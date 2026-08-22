"""
TourSafe Primary Copilot Orchestration Service.
Orchestrates authenticated sessions, bounded conversation histories,
LLM tool planning, safe multi-step execution, grounded synthesis,
RAG citations, action previews, and comprehensive auditing.
"""

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from ...core.config import settings
from ...core.database import get_database
from ...models.copilot import (
    ActionProposal,
    CitationSource,
    CopilotMessage,
    CopilotSession,
    CopilotSessionStatus,
    MessageRole,
    ToolCallRecord,
    ToolResultRecord,
)
from .action_manager import action_manager
from .audit_service import copilot_audit_service
from .context_manager import context_manager
from .llm_provider import get_llm_provider
from .rag_service import rag_service
from .tool_registry import copilot_tool_registry

logger = logging.getLogger(__name__)


class CopilotService:
    """Core operational intelligence and decision-support orchestrator."""

    async def init_indexes(self) -> None:
        db = get_database()
        coll_ses = db["copilot_sessions"]
        await coll_ses.create_index("session_id", unique=True)
        await coll_ses.create_index("user_id")
        await coll_ses.create_index("jurisdiction_id")
        await coll_ses.create_index("updated_at")

        coll_msg = db["copilot_messages"]
        await coll_msg.create_index("message_id", unique=True)
        await coll_msg.create_index("session_id")
        await coll_msg.create_index("timestamp")

        await action_manager.init_indexes()
        await copilot_audit_service.init_indexes()
        await rag_service.init_indexes()

    # -------------------------------------------------------------
    # SESSION MANAGEMENT
    # -------------------------------------------------------------

    async def create_session(
        self,
        user_id: str,
        organization_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        title: str = "Authority Operational Assistance",
        active_incident_id: Optional[str] = None,
        active_zone_id: Optional[str] = None,
        active_responder_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CopilotSession:
        """Create a scoped Copilot session for an authorized authority operator."""
        session = CopilotSession(
            user_id=user_id,
            organization_id=organization_id,
            jurisdiction_id=jurisdiction_id,
            title=title,
            active_incident_id=active_incident_id,
            active_zone_id=active_zone_id,
            active_responder_id=active_responder_id,
            metadata=metadata or {},
        )
        db = get_database()
        await db["copilot_sessions"].insert_one(session.to_dict())

        # Welcome message
        welcome = CopilotMessage(
            session_id=session.session_id,
            role=MessageRole.ASSISTANT,
            content=(
                "**TourSafe Authority Copilot Online**.\n\n"
                "I am your database-grounded operational decision support assistant. "
                "All responses reflect live telemetry, verified incidents, risk episodes, "
                "responder fleet readiness, and approved SOP documentation.\n\n"
                "You may query current incidents, request situational summaries, examine risk factors, "
                "or review response procedures."
            ),
            data_freshness="Realtime Grounded",
        )
        await db["copilot_messages"].insert_one(welcome.to_dict())

        return session

    async def get_session(
        self,
        session_id: str,
        user_id: str,
        role: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve session ensuring RBAC access boundary."""
        db = get_database()
        ses = await db["copilot_sessions"].find_one({"session_id": session_id})
        if not ses:
            return None

        # User must own the session unless admin
        if ses["user_id"] != user_id and role.lower() != "admin":
            return None

        ses["_id"] = str(ses.get("_id", ""))
        return ses

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List active sessions for the current user."""
        db = get_database()
        cursor = db["copilot_sessions"].find({"user_id": user_id, "status": "active"}).sort("updated_at", -1).limit(limit)
        sessions = await cursor.to_list(length=limit)
        for s in sessions:
            s["_id"] = str(s.get("_id", ""))
        return sessions

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve message history for a session."""
        db = get_database()
        cursor = db["copilot_messages"].find({"session_id": session_id}).sort("timestamp", 1).limit(limit)
        msgs = await cursor.to_list(length=limit)
        for m in msgs:
            m["_id"] = str(m.get("_id", ""))
        return msgs

    # -------------------------------------------------------------
    # AGENTIC EXECUTION & MESSAGE PROCESSING
    # -------------------------------------------------------------

    async def process_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        user_text: str,
        active_incident_id: Optional[str] = None,
        active_zone_id: Optional[str] = None,
        active_responder_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> CopilotMessage:
        """
        Execute full agentic decision-support pipeline:
        1. Context and RBAC injection
        2. Prompt injection defense
        3. Multi-turn tool planning and safe invocation
        4. Action proposal generation (preview only)
        5. Grounded synthesis with citations & freshness
        6. Immutable auditing
        """
        start_time = time.time()
        db = get_database()

        # Sanitize input against prompt injection
        sanitized_query = context_manager.sanitize_user_input(user_text)

        # 1. Store User Message
        user_msg = CopilotMessage(
            session_id=session_id,
            role=MessageRole.USER,
            content=sanitized_query,
            metadata={
                "active_incident_id": active_incident_id,
                "active_zone_id": active_zone_id,
                "active_responder_id": active_responder_id,
            },
        )
        await db["copilot_messages"].insert_one(user_msg.to_dict())

        # 2. Build Execution Context
        authority_context = {
            "user_id": user_id,
            "role": role,
            "organization_id": organization_id,
            "jurisdiction_id": jurisdiction_id,
            "active_incident_id": active_incident_id,
            "active_zone_id": active_zone_id,
            "active_responder_id": active_responder_id,
        }

        # Load recent message history
        raw_msgs = await self.get_messages(session_id, limit=12)
        model_history: List[Dict[str, Any]] = [context_manager.build_system_message(authority_context)]

        for rm in raw_msgs:
            model_history.append({
                "role": rm.get("role", "user"),
                "content": rm.get("content", ""),
                "metadata": rm.get("metadata", {}),
            })

        # 3. Retrieve Authorized Tools
        authorized_tools = copilot_tool_registry.get_authorized_tool_schemas(role)
        llm = get_llm_provider()

        tool_calls_accumulated: List[ToolCallRecord] = []
        tool_results_accumulated: List[ToolResultRecord] = []
        citations_accumulated: List[CitationSource] = []
        action_proposal_created: Optional[ActionProposal] = None
        uncertainty_notes: List[str] = []
        executed_tool_signatures: Set[str] = set()

        max_turns = getattr(settings, "copilot_max_tool_calls_per_turn", 6)
        final_content = ""
        total_tokens_in = 0
        total_tokens_out = 0

        # Multi-Step Tool Invocation Loop
        for turn_idx in range(max_turns):
            llm_resp = await llm.generate(
                messages=model_history,
                tools=authorized_tools,
                temperature=settings.copilot_temperature,
                max_tokens=settings.copilot_max_tokens,
            )

            total_tokens_in += llm_resp.tokens_input
            total_tokens_out += llm_resp.tokens_output

            if not llm_resp.tool_calls:
                # Terminal synthesis reached
                final_content = llm_resp.content
                break

            # Process Tool Calls requested by LLM
            for tc in llm_resp.tool_calls:
                t_name = tc.get("name")
                t_args = tc.get("arguments", {})

                # Loop detection: check if exact tool + args was already called in this turn
                sig = f"{t_name}:{json.dumps(t_args, sort_keys=True)}"
                if sig in executed_tool_signatures:
                    logger.warning(f"Detected tool call loop for signature '{sig}', breaking loop.")
                    continue
                executed_tool_signatures.add(sig)

                tc_rec = ToolCallRecord(tool_name=t_name, arguments=t_args)
                tool_calls_accumulated.append(tc_rec)

                # Special Handling: Action Proposal Interception (Action Tools)
                if t_name == "propose_dispatch_responder":
                    inc_id = t_args.get("incident_id") or active_incident_id or "inc_active"
                    resp_id = t_args.get("responder_id") or active_responder_id or "resp_unit_1"
                    reason = t_args.get("reason", "Operator requested dispatch via AI Copilot")
                    proposal = await action_manager.propose_action(
                        session_id=session_id,
                        user_id=user_id,
                        tool_name=t_name,
                        action_type="dispatch_responder",
                        target_id=inc_id,
                        target_description=f"Unit {resp_id} to Incident {inc_id}",
                        reason=reason,
                        expected_effect=f"Assigns responder '{resp_id}' to incident '{inc_id}' and starts SLA timer.",
                        parameters={"incident_id": inc_id, "responder_id": resp_id},
                        organization_id=organization_id,
                        jurisdiction_id=jurisdiction_id,
                    )
                    action_proposal_created = proposal
                    t_result = {
                        "success": True,
                        "data": proposal.to_dict(),
                        "source": "Action Proposal Engine",
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                    }

                elif t_name == "propose_escalate_incident":
                    inc_id = t_args.get("incident_id") or active_incident_id or "inc_active"
                    level = t_args.get("escalation_level", "stage2_supervisor")
                    reason = t_args.get("reason", "Operator requested escalation via AI Copilot")
                    proposal = await action_manager.propose_action(
                        session_id=session_id,
                        user_id=user_id,
                        tool_name=t_name,
                        action_type="escalate_incident",
                        target_id=inc_id,
                        target_description=f"Escalate Incident {inc_id} to {level}",
                        reason=reason,
                        expected_effect=f"Triggers stage 2 supervisor escalation and broadcasts priority alerts.",
                        parameters={"incident_id": inc_id, "escalation_level": level, "reason": reason},
                        organization_id=organization_id,
                        jurisdiction_id=jurisdiction_id,
                    )
                    action_proposal_created = proposal
                    t_result = {
                        "success": True,
                        "data": proposal.to_dict(),
                        "source": "Action Proposal Engine",
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                    }

                else:
                    # Execute Standard Read-Only Tool
                    t_result = await copilot_tool_registry.execute_tool(
                        tool_name=t_name,
                        arguments=t_args,
                        user_context=authority_context,
                    )

                # Record Tool Result
                tr_rec = ToolResultRecord(
                    call_id=tc_rec.call_id,
                    tool_name=t_name,
                    success=t_result.get("success", True),
                    data=t_result.get("data"),
                    error=t_result.get("error"),
                    source=t_result.get("source", "TourSafe Tool"),
                    observed_at=t_result.get("observed_at"),
                    latency_ms=t_result.get("latency_ms", 0.0),
                )
                tool_results_accumulated.append(tr_rec)

                # Audit tool execution
                await copilot_audit_service.log_event(
                    user_id=user_id,
                    session_id=session_id,
                    role=role,
                    action="tool_executed",
                    tool_name=t_name,
                    input_params=t_args,
                    result_summary=f"Success: {tr_rec.success}",
                    authorization_passed=True,
                    jurisdiction_id=jurisdiction_id,
                    latency_ms=tr_rec.latency_ms,
                )

                # Extract citations if knowledge base or specific entity was queried
                if t_name == "search_knowledge_base" and tr_rec.data:
                    for doc in tr_rec.data:
                        citations_accumulated.append(CitationSource(
                            source_type="document",
                            title=doc.get("title", "Knowledge Document"),
                            identifier=doc.get("document_id"),
                            version=doc.get("version"),
                            section=doc.get("section"),
                            snippet=doc.get("snippet", "")[:120],
                        ))
                elif tr_rec.source:
                    citations_accumulated.append(CitationSource(
                        source_type="data_source",
                        title=tr_rec.source,
                        identifier=t_name,
                        freshness=tr_rec.observed_at or "Realtime",
                    ))

                # Handle failure / uncertainty
                if not tr_rec.success:
                    if tr_rec.error == "TIMEOUT":
                        uncertainty_notes.append(f"Query on `{t_name}` timed out.")
                    elif tr_rec.error == "UNAUTHORIZED":
                        uncertainty_notes.append(f"Access to `{t_name}` restricted by policy.")

                # Feed tool result back to model history
                model_history.append({
                    "role": "TOOL",
                    "tool_name": t_name,
                    "name": t_name,
                    "content": json.dumps(t_result),
                })

        # If LLM didn't synthesize final content yet (e.g. max turns reached), do one final synthesis call
        if not final_content:
            fallback_resp = await llm.generate(
                messages=model_history,
                tools=None,
                temperature=settings.copilot_temperature,
                max_tokens=settings.copilot_max_tokens,
            )
            final_content = fallback_resp.content

        total_latency = (time.time() - start_time) * 1000

        # Determine data freshness
        freshness_label = "Updated: Just now"
        if tool_results_accumulated:
            observed_times = [r.observed_at for r in tool_results_accumulated if r.observed_at]
            if observed_times:
                freshness_label = f"Observed at {observed_times[-1]}"

        # 4. Store Assistant Message
        assistant_msg = CopilotMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=final_content,
            citations=citations_accumulated,
            tool_calls=tool_calls_accumulated,
            tool_results=tool_results_accumulated,
            action_proposal=action_proposal_created,
            data_freshness=freshness_label,
            uncertainty_note="; ".join(uncertainty_notes) if uncertainty_notes else None,
            tokens_input=total_tokens_in,
            tokens_output=total_tokens_out,
            latency_ms=total_latency,
            model=getattr(llm, "model_name", "toursafe-agentic-v1"),
        )
        await db["copilot_messages"].insert_one(assistant_msg.to_dict())

        # 5. Update Session metadata
        await db["copilot_sessions"].update_one(
            {"session_id": session_id},
            {
                "$inc": {"message_count": 2},
                "$set": {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "active_incident_id": active_incident_id,
                    "active_zone_id": active_zone_id,
                    "active_responder_id": active_responder_id,
                },
            },
        )

        # 6. Audit Query Completion
        await copilot_audit_service.log_event(
            user_id=user_id,
            session_id=session_id,
            role=role,
            action="query_completed",
            result_summary=f"Tools called: {len(tool_calls_accumulated)}, Citations: {len(citations_accumulated)}",
            authorization_passed=True,
            jurisdiction_id=jurisdiction_id,
            latency_ms=total_latency,
        )

        return assistant_msg


copilot_service = CopilotService()
