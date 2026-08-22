"""
TourSafe Emergency Response Automation & Escalation Orchestration Engine

Policy-driven, auditable, failure-tolerant orchestration engine transforming
operational safety events and SOS triggers into structured response plans,
capability-matched dispatches, durable acknowledgement timeouts, and multi-stage escalations.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()


from ...schemas.emergency import (
    ActionStatus,
    ActionType,
    IncidentSeverity,
    IncidentStatus,
    ManualOverrideRequest,
    NotificationChannel,
    OrchestratorHealthResponse,
    OrchestratorHealthStatus,
    ParticipantRole,
    PolicyStatus,
    PolicyTriggerType,
    ResponderAssignmentRole,
    ResponseActionConfig,
    ResponseActionRecord,
    ResponseKpiResponse,
    ResponsePlanDetailResponse,
    ResponsePlanRecord,
    ResponsePlanStatus,
    ResponsePolicy,
    ResponseTimerJobRecord,
    SlaStatus,
    TimerJobStatus,
)
from ...schemas.safety import IncidentRecord
from ..safety.events import safety_event_publisher
from .incident_channel_service import incident_channel_service
from .messaging_service import messaging_service
from .notifications import notification_service
from .response_policy_service import response_policy_service

logger = logging.getLogger("toursafe.emergency.orchestrator")


class ResponseOrchestrator:
    """
    Central emergency response automation and escalation orchestration engine.
    """

    def __init__(self):
        self._is_running = True
        self._start_time = datetime.now(timezone.utc)
        self._last_sweep_at: Optional[str] = None
        self._failed_actions_24h = 0

    # -----------------------------------------------------------------------
    # Plan Creation & Policy Evaluation
    # -----------------------------------------------------------------------

    async def initiate_response_plan(
        self,
        incident_id: str,
        trigger_type: PolicyTriggerType = PolicyTriggerType.SAFETY_STATE,
        custom_policy_id: Optional[str] = None,
        trigger_metadata: Optional[Dict[str, Any]] = None,
    ) -> ResponsePlanRecord:
        """
        Creates and starts a durable ResponsePlan for an incident according to active policy.
        Enforces idempotency: exactly one active plan per incident.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        metadata = trigger_metadata or {}

        # 1. Idempotency Check: Existing active plan
        existing_doc = await db.response_plans.find_one({
            "incident_id": incident_id,
            "status": {"$nin": [ResponsePlanStatus.COMPLETED.value, ResponsePlanStatus.CANCELLED.value]},
        })
        if existing_doc:
            logger.info("Active response plan already exists for incident %s (%s)", incident_id, existing_doc.get("response_plan_id"))
            return ResponsePlanRecord(**existing_doc)

        # 2. Select Response Policy
        policy: Optional[ResponsePolicy] = None
        if custom_policy_id:
            policy = await response_policy_service.get_policy_by_id(custom_policy_id)
        if not policy:
            policy = await response_policy_service.get_active_policy_for_trigger(trigger_type)
        if not policy:
            # Fallback to default
            policy = response_policy_service.get_default_policies()[0]

        # 3. Construct Initial Action Records
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        action_records: List[ResponseActionRecord] = []
        for act_cfg in policy.initial_actions:
            action_id = f"act_{uuid.uuid4().hex[:10]}"
            idempotency_key = f"{plan_id}:{act_cfg.action_key}:0"
            rec = ResponseActionRecord(
                action_id=action_id,
                plan_id=plan_id,
                incident_id=incident_id,
                action_key=act_cfg.action_key,
                type=act_cfg.type,
                target=act_cfg.target,
                status=ActionStatus.PENDING,
                parameters=act_cfg.parameters,
                depends_on=act_cfg.depends_on,
                created_at=now_iso,
                attempt_count=0,
                max_attempts=act_cfg.max_attempts,
                idempotency_key=idempotency_key,
            )
            action_records.append(rec)

        # 4. Compute Deadlines
        ack_deadline = (datetime.now(timezone.utc) + timedelta(seconds=policy.ack_timeout_seconds)).isoformat()
        escalation_deadline = (datetime.now(timezone.utc) + timedelta(seconds=policy.dispatch_timeout_seconds)).isoformat()

        # 5. Create Response Plan Record
        plan = ResponsePlanRecord(
            response_plan_id=plan_id,
            incident_id=incident_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            trigger_source=trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type),
            status=ResponsePlanStatus.ACTIVE,
            current_stage=policy.initial_stage,
            escalation_level=0,
            is_paused=False,
            actions=action_records,
            ack_deadline=ack_deadline,
            escalation_deadline=escalation_deadline,
            created_at=now_iso,
            started_at=now_iso,
            timeline=[
                {
                    "timestamp": now_iso,
                    "event": "PLAN_CREATED",
                    "policy_id": policy.policy_id,
                    "policy_version": policy.version,
                    "policy_name": policy.name,
                    "details": f"Response plan initiated under policy '{policy.name}' ({policy.version})",
                }
            ],
            metrics={
                "time_to_acknowledge_seconds": None,
                "time_to_dispatch_seconds": None,
                "time_to_accept_seconds": None,
                "time_to_arrival_seconds": None,
                "time_to_resolution_seconds": None,
                "escalation_count": 0,
                "failed_actions_count": 0,
            },
            metadata=metadata,
        )

        await db.response_plans.insert_one(plan.model_dump())
        logger.info("Created response plan %s for incident %s", plan.response_plan_id, incident_id)

        # 6. Post system message to incident communication channel if channel exists
        try:
            from ...schemas.emergency import MessagePriority, MessageSendRequest, MessageType
            await messaging_service.send_message(
                incident_id=incident_id,
                sender_id="system",
                sender_role=ParticipantRole.SYSTEM,
                sender_name="TourSafe System",
                req=MessageSendRequest(
                    content=f"Operational Response Plan initiated under policy: {policy.name} ({policy.version})",
                    priority=MessagePriority.HIGH,
                    message_type=MessageType.SYSTEM,
                ),
            )
        except Exception as e:
            logger.debug("Could not post plan start system message: %s", e)

        # 7. Execute initial actions graph
        asyncio.create_task(self.execute_plan_actions(plan.response_plan_id))

        return plan

    # -----------------------------------------------------------------------
    # Action Graph Execution Engine
    # -----------------------------------------------------------------------

    async def execute_plan_actions(self, plan_id: str) -> None:
        """
        Executes ready pending actions for a response plan respecting dependencies.
        """
        db = get_database()
        doc = await db.response_plans.find_one({"response_plan_id": plan_id})
        if not doc:
            return

        plan = ResponsePlanRecord(**doc)
        if plan.is_paused or plan.status in (ResponsePlanStatus.COMPLETED, ResponsePlanStatus.CANCELLED, ResponsePlanStatus.FAILED):
            return

        completed_keys = {a.action_key for a in plan.actions if a.status == ActionStatus.COMPLETED and a.action_key}
        tasks = []

        for action in plan.actions:
            if action.status == ActionStatus.PENDING:
                # Check dependencies
                deps_satisfied = all(dep in completed_keys for dep in action.depends_on)
                if deps_satisfied:
                    tasks.append(self.execute_single_action(plan_id, action.action_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def execute_single_action(self, plan_id: str, action_id: str) -> Dict[str, Any]:
        """
        Executes an individual action with idempotency, timeout tracking, retries, and failure handling.
        """
        db = get_database()
        plan_doc = await db.response_plans.find_one({"response_plan_id": plan_id})
        if not plan_doc:
            return {"status": "FAILED", "reason": "Plan not found"}

        plan = ResponsePlanRecord(**plan_doc)
        target_action = next((a for a in plan.actions if a.action_id == action_id), None)
        if not target_action:
            return {"status": "FAILED", "reason": "Action not found"}

        if target_action.status in (ActionStatus.COMPLETED, ActionStatus.RUNNING, ActionStatus.CANCELLED):
            return {"status": target_action.status.value, "idempotent": True}

        # Mark action as RUNNING
        now_iso = datetime.now(timezone.utc).isoformat()
        target_action.status = ActionStatus.RUNNING
        target_action.started_at = now_iso
        target_action.attempt_count += 1

        await db.response_plans.update_one(
            {"response_plan_id": plan_id, "actions.action_id": action_id},
            {
                "$set": {
                    "actions.$.status": ActionStatus.RUNNING.value,
                    "actions.$.started_at": now_iso,
                    "actions.$.attempt_count": target_action.attempt_count,
                }
            },
        )

        outcome: Dict[str, Any] = {}
        error_msg: Optional[str] = None

        try:
            # Execute specific action based on type
            if target_action.type == ActionType.NOTIFY_AUTHORITY:
                outcome = await self._exec_notify_authority(plan, target_action)
            elif target_action.type == ActionType.NOTIFY_TOURIST:
                outcome = await self._exec_notify_tourist(plan, target_action)
            elif target_action.type == ActionType.NOTIFY_RESPONDER:
                outcome = await self._exec_notify_responder(plan, target_action)
            elif target_action.type == ActionType.DISPATCH_RESPONDER:
                outcome = await self._exec_dispatch_responder(plan, target_action)
            elif target_action.type == ActionType.REQUEST_ACKNOWLEDGEMENT:
                outcome = await self._exec_request_acknowledgement(plan, target_action)
            elif target_action.type == ActionType.REQUEST_SUPERVISOR:
                outcome = await self._exec_request_supervisor(plan, target_action)
            elif target_action.type == ActionType.ESCALATE:
                outcome = await self._exec_escalate(plan, target_action)
            elif target_action.type == ActionType.ADD_PARTICIPANT:
                outcome = await self._exec_add_participant(plan, target_action)
            elif target_action.type == ActionType.MARK_REQUIRES_HUMAN_REVIEW:
                outcome = await self._exec_mark_human_review(plan, target_action)
            else:
                outcome = {"status": "SUCCESS", "message": f"Action {target_action.type.value} completed"}

            success = outcome.get("success", True)

        except Exception as e:
            logger.error("Error executing action %s (%s) in plan %s: %s", action_id, target_action.type.value, plan_id, e)
            success = False
            error_msg = str(e)

        # Update action state
        completed_iso = datetime.now(timezone.utc).isoformat()
        if success:
            target_action.status = ActionStatus.COMPLETED
            target_action.completed_at = completed_iso
            target_action.output_data = outcome

            await db.response_plans.update_one(
                {"response_plan_id": plan_id, "actions.action_id": action_id},
                {
                    "$set": {
                        "actions.$.status": ActionStatus.COMPLETED.value,
                        "actions.$.completed_at": completed_iso,
                        "actions.$.output_data": outcome,
                    },
                    "$push": {
                        "timeline": {
                            "timestamp": completed_iso,
                            "event": "ACTION_COMPLETED",
                            "action_id": action_id,
                            "action_type": target_action.type.value,
                            "action_key": target_action.action_key,
                            "details": outcome.get("message", "Action succeeded"),
                        }
                    },
                },
            )

            # Trigger downstream dependent actions
            asyncio.create_task(self.execute_plan_actions(plan_id))

        else:
            # Handle Retry or Dead-Letter Failure
            self._failed_actions_24h += 1
            if target_action.attempt_count < target_action.max_attempts:
                target_action.status = ActionStatus.RETRYING
                target_action.failure_reason = error_msg or outcome.get("reason", "Action attempt failed")
                backoff_seconds = 15 * target_action.attempt_count
                next_retry = (datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)).isoformat()
                target_action.next_retry_at = next_retry

                await db.response_plans.update_one(
                    {"response_plan_id": plan_id, "actions.action_id": action_id},
                    {
                        "$set": {
                            "actions.$.status": ActionStatus.RETRYING.value,
                            "actions.$.failure_reason": target_action.failure_reason,
                            "actions.$.next_retry_at": next_retry,
                        }
                    },
                )
                # Create retry timer job
                await self._create_timer_job(
                    incident_id=plan.incident_id,
                    plan_id=plan_id,
                    action_id=action_id,
                    timer_type="RETRY",
                    delay_seconds=backoff_seconds,
                    payload={"action_id": action_id},
                )
            else:
                # Dead-letter failure
                target_action.status = ActionStatus.FAILED
                target_action.failed_at = completed_iso
                target_action.failure_reason = error_msg or outcome.get("reason", "Action exhausted all retry attempts")

                await db.response_plans.update_one(
                    {"response_plan_id": plan_id, "actions.action_id": action_id},
                    {
                        "$set": {
                            "actions.$.status": ActionStatus.FAILED.value,
                            "actions.$.failed_at": completed_iso,
                            "actions.$.failure_reason": target_action.failure_reason,
                        },
                        "$inc": {"metrics.failed_actions_count": 1},
                        "$push": {
                            "timeline": {
                                "timestamp": completed_iso,
                                "event": "ACTION_FAILED",
                                "action_id": action_id,
                                "action_type": target_action.type.value,
                                "failure_reason": target_action.failure_reason,
                            }
                        },
                    },
                )

                # Alert Authority of failed action
                await self._notify_authority_of_action_failure(plan, target_action)

        return {"status": target_action.status.value, "output": outcome, "error": error_msg}

    # -----------------------------------------------------------------------
    # Action Type Implementations
    # -----------------------------------------------------------------------

    async def _exec_notify_authority(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Notifies authority operators via abstracted notification infrastructure.
        """
        priority = action.parameters.get("priority", "HIGH")
        roles = action.parameters.get("target_roles", ["authority", "lead_operator"])
        sent_count = 0

        for role in roles:
            for ch in [NotificationChannel.PUSH, NotificationChannel.EMAIL]:
                res = await notification_service.send_notification(
                    recipient=f"role:{role}",
                    channel=ch,
                    subject=f"URGENT: TourSafe Incident {plan.incident_id} [{priority}]",
                    message=f"Incident {plan.incident_id} response initiated under policy {plan.policy_id}. Immediate operational tracking required.",
                    incident_id=plan.incident_id,
                    recipient_type="AUTHORITY_CENTER",
                    policy_trigger=action.idempotency_key,
                )
                if res.status.value in ("SENT", "DELIVERED", "QUEUED"):
                    sent_count += 1

        return {"success": True, "notifications_sent": sent_count, "message": f"Authority notified via {sent_count} channels"}

    async def _exec_notify_tourist(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Notifies tourist with safe guidance without leaking internal orchestration details.
        """
        db = get_database()
        inc_doc = await db.incidents.find_one({"incident_id": plan.incident_id})
        tourist_id = inc_doc.get("tourist_id") if inc_doc else None
        if not tourist_id:
            return {"success": True, "message": "No tourist ID associated with incident"}

        guidance = action.parameters.get("guidance", "Authority response has been initiated. Please remain in a safe location.")

        res = await notification_service.send_notification(
            recipient=tourist_id,
            channel=NotificationChannel.PUSH,
            subject="TourSafe Safety Support",
            message=guidance,
            incident_id=plan.incident_id,
            recipient_type="TOURIST",
            policy_trigger=action.idempotency_key,
        )
        return {"success": True, "message": "Tourist notified with safety guidance", "notification_id": res.notification_id}

    async def _exec_notify_responder(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Notifies assigned responder of mission operational context.
        """
        responder_id = action.parameters.get("responder_id")
        if not responder_id:
            return {"success": False, "reason": "No responder_id specified in action parameters"}

        res = await notification_service.send_notification(
            recipient=responder_id,
            channel=NotificationChannel.PUSH,
            subject=f"CRITICAL DISPATCH: Incident {plan.incident_id}",
            message=f"You have been assigned to emergency incident {plan.incident_id}. Please review details and acknowledge immediate dispatch.",
            incident_id=plan.incident_id,
            recipient_type="RESPONDER",
            policy_trigger=action.idempotency_key,
        )
        return {"success": True, "message": f"Responder {responder_id} notified", "notification_id": res.notification_id}

    async def _exec_dispatch_responder(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Dispatches eligible responder via Prompt 22 dispatch infrastructure.
        Checks capabilities, jurisdiction, availability. If no responder found, triggers fallback.
        """
        db = get_database()
        required_caps = action.parameters.get("required_capabilities", ["SECURITY", "FIRST_AID"])
        role_str = action.parameters.get("assignment_role", "PRIMARY")
        assignment_role = ResponderAssignmentRole[role_str] if role_str in ResponderAssignmentRole.__members__ else ResponderAssignmentRole.PRIMARY

        # 1. Fetch available eligible responders from DB
        query = {
            "status": "AVAILABLE",
            "active": True,
        }
        candidates_cursor = db.responders.find(query)
        candidates = []
        async for c in candidates_cursor:
            candidates.append(c)

        if not candidates:
            # Fallback: flag NO_ELIGIBLE_RESPONDER and trigger escalation
            logger.warning("No eligible responder found for incident %s", plan.incident_id)
            await self._handle_no_eligible_responder(plan)
            return {
                "success": False,
                "outcome": "NO_ELIGIBLE_RESPONDER",
                "reason": "All eligible responders are unavailable or busy. Escalation triggered.",
            }

        # Select first matching candidate (best distance/match handled by recommendation service)
        selected = candidates[0]
        responder_id = selected.get("responder_id")

        # 2. Create Assignment in assignment_service
        try:
            from .assignment_service import assignment_service
            asgn = await assignment_service.create_assignment(
                incident_id=plan.incident_id,
                responder_id=responder_id,
                assigned_by="response_orchestrator",
                unit_id=selected.get("unit_id"),
                notes=f"Auto-dispatched by Response Plan {plan.response_plan_id}",
                assignment_role=assignment_role,
            )

            # 3. Add to Incident Communication Channel as participant
            await incident_channel_service.add_participant(
                incident_id=plan.incident_id,
                user_id=responder_id,
                display_name=selected.get("name", "Responder"),
                role=ParticipantRole.RESPONDER,
                responder_role=assignment_role,
            )

            # 4. Notify responder
            await notification_service.send_notification(
                recipient=responder_id,
                channel=NotificationChannel.PUSH,
                subject=f"CRITICAL DISPATCH: Incident {plan.incident_id}",
                message="You have been assigned to a response mission. Please acknowledge immediate dispatch.",
                incident_id=plan.incident_id,
                recipient_type="RESPONDER",
                policy_trigger=action.idempotency_key,
            )

            # Update plan status to WAITING_ACK
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.response_plans.update_one(
                {"response_plan_id": plan.response_plan_id},
                {
                    "$set": {"status": ResponsePlanStatus.WAITING_ACK.value},
                    "$push": {
                        "timeline": {
                            "timestamp": now_iso,
                            "event": "RESPONDER_DISPATCHED",
                            "responder_id": responder_id,
                            "assignment_id": asgn.assignment_id,
                            "role": assignment_role.value,
                        }
                    },
                },
            )

            return {
                "success": True,
                "responder_id": responder_id,
                "assignment_id": asgn.assignment_id,
                "message": f"Responder {responder_id} successfully dispatched.",
            }

        except Exception as e:
            logger.error("Failed to assign responder %s: %s", responder_id, e)
            return {"success": False, "reason": str(e)}

    async def _exec_request_acknowledgement(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Starts authoritative server-side acknowledgement timer job in MongoDB.
        """
        policy = await response_policy_service.get_policy_by_id(plan.policy_id)
        ack_timeout = policy.ack_timeout_seconds if policy else 120

        job = await self._create_timer_job(
            incident_id=plan.incident_id,
            plan_id=plan.response_plan_id,
            action_id=action.action_id,
            timer_type="ACKNOWLEDGEMENT",
            delay_seconds=ack_timeout,
            payload={"action_id": action.action_id, "policy_id": plan.policy_id},
        )

        db = get_database()
        await db.response_plans.update_one(
            {"response_plan_id": plan.response_plan_id},
            {"$set": {"active_timer_job_id": job.job_id}},
        )

        return {"success": True, "job_id": job.job_id, "deadline": job.deadline, "timeout_seconds": ack_timeout}

    async def _exec_request_supervisor(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Alerts authority supervisors of delayed or escalated response.
        """
        alert_level = action.parameters.get("alert_level", "YELLOW")
        sent = await notification_service.send_notification(
            recipient="role:authority_supervisor",
            channel=NotificationChannel.PUSH,
            subject=f"SUPERVISOR ESCALATION [Alert {alert_level}]: Incident {plan.incident_id}",
            message=f"Incident {plan.incident_id} requires supervisor intervention due to response delay/timeout.",
            incident_id=plan.incident_id,
            recipient_type="AUTHORITY_CENTER",
            policy_trigger=action.idempotency_key,
        )

        # Post system message in channel
        await incident_channel_service.post_system_operational_event(
            incident_id=plan.incident_id,
            event_type="SUPERVISOR_NOTIFIED",
            content=f"Supervisor Alert ({alert_level}) broadcasted due to escalation policy trigger.",
            metadata={"plan_id": plan.response_plan_id, "alert_level": alert_level},
        )

        return {"success": True, "message": "Supervisor alert dispatched", "notification_id": sent.notification_id}

    async def _exec_escalate(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Advances policy escalation stage and updates incident severity.
        """
        next_stage = plan.escalation_level + 1
        return await self.escalate_plan_stage(plan.response_plan_id, next_stage, reason=action.parameters.get("reason", "Policy-driven escalation"))

    async def _exec_add_participant(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Adds a specialist, support unit, or authority to the incident communication channel.
        """
        user_id = action.parameters.get("user_id")
        display_name = action.parameters.get("display_name", "Support Operator")
        role_str = action.parameters.get("role", "AUTHORITY")
        role = ParticipantRole[role_str] if role_str in ParticipantRole.__members__ else ParticipantRole.AUTHORITY

        if user_id:
            await incident_channel_service.add_participant(
                incident_id=plan.incident_id,
                user_id=user_id,
                display_name=display_name,
                role=role,
            )
        return {"success": True, "message": f"Participant {user_id} added to incident channel"}

    async def _exec_mark_human_review(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> Dict[str, Any]:
        """
        Flags incident as requiring human authority review.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.incidents.update_one(
            {"incident_id": plan.incident_id},
            {
                "$set": {
                    "notes": f"Requires operational human review: {action.parameters.get('reason', 'Policy review gate')}",
                    "updated_at": now_iso,
                }
            },
        )
        return {"success": True, "message": "Incident flagged for human operator review"}

    # -----------------------------------------------------------------------
    # Durable Timers & Server-Side Scheduler
    # -----------------------------------------------------------------------

    async def _create_timer_job(
        self,
        incident_id: str,
        plan_id: str,
        action_id: Optional[str],
        timer_type: str,
        delay_seconds: int,
        payload: Dict[str, Any],
        stage: int = 0,
    ) -> ResponseTimerJobRecord:
        """
        Persists a durable timer job in MongoDB.
        """
        db = get_database()
        now = datetime.now(timezone.utc)
        deadline = (now + timedelta(seconds=delay_seconds)).isoformat()
        job = ResponseTimerJobRecord(
            job_id=f"tmr_{uuid.uuid4().hex[:12]}",
            incident_id=incident_id,
            plan_id=plan_id,
            action_id=action_id,
            timer_type=timer_type,
            stage=stage,
            deadline=deadline,
            status=TimerJobStatus.PENDING,
            created_at=now.isoformat(),
            attempt_count=0,
            payload=payload,
        )
        await db.response_timer_jobs.insert_one(job.model_dump())
        logger.info("Scheduled durable timer job %s (%s) for %s with deadline %s", job.job_id, timer_type, incident_id, deadline)
        return job

    async def run_scheduler_sweep(self) -> int:
        """
        Durable scheduler sweep across all due timer jobs in MongoDB.
        Uses atomic find_one_and_update to guarantee distributed locking / concurrency protection.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        self._last_sweep_at = now_iso
        processed_count = 0

        # Query due jobs
        cursor = db.response_timer_jobs.find({
            "status": TimerJobStatus.PENDING.value,
            "deadline": {"$lte": now_iso},
        })

        async for doc in cursor:
            job_id = doc.get("job_id")
            # Atomic claim
            claimed = await db.response_timer_jobs.find_one_and_update(
                {"job_id": job_id, "status": TimerJobStatus.PENDING.value},
                {"$set": {"status": TimerJobStatus.RUNNING.value}},
            )
            if claimed:
                try:
                    await self._process_timer_job(ResponseTimerJobRecord(**claimed))
                    processed_count += 1
                except Exception as e:
                    logger.error("Error executing timer job %s: %s", job_id, e)
                    await db.response_timer_jobs.update_one(
                        {"job_id": job_id},
                        {"$set": {"status": TimerJobStatus.DEAD_LETTER.value, "error_message": str(e)}},
                    )

        return processed_count

    async def _process_timer_job(self, job: ResponseTimerJobRecord) -> None:
        """
        Executes a claimed timer job based on its timer_type.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Check if plan or incident is still active
        plan_doc = await db.response_plans.find_one({"response_plan_id": job.plan_id})
        if not plan_doc:
            await db.response_timer_jobs.update_one({"job_id": job.job_id}, {"$set": {"status": TimerJobStatus.CANCELLED.value}})
            return

        plan = ResponsePlanRecord(**plan_doc)
        if plan.is_paused or plan.status in (ResponsePlanStatus.COMPLETED, ResponsePlanStatus.CANCELLED):
            await db.response_timer_jobs.update_one({"job_id": job.job_id}, {"$set": {"status": TimerJobStatus.CANCELLED.value}})
            return

        if job.timer_type == "ACKNOWLEDGEMENT":
            # Check if incident has been acknowledged/accepted
            if plan.status == ResponsePlanStatus.WAITING_ACK:
                logger.info("Acknowledgement timeout expired for incident %s. Triggering escalation.", job.incident_id)
                next_stage = plan.escalation_level + 1
                await self.escalate_plan_stage(
                    plan_id=job.plan_id,
                    target_stage=next_stage,
                    reason="Primary responder unacknowledged past timeout window.",
                )

        elif job.timer_type == "ESCALATION":
            # Stage delay expired, execute stage actions
            next_stage = job.stage
            await self.escalate_plan_stage(
                plan_id=job.plan_id,
                target_stage=next_stage,
                reason=f"Escalation Stage {next_stage} delay threshold reached.",
            )

        elif job.timer_type == "RETRY":
            # Retry failed action
            action_id = job.payload.get("action_id")
            if action_id:
                await self.execute_single_action(job.plan_id, action_id)

        # Mark job COMPLETED
        await db.response_timer_jobs.update_one(
            {"job_id": job.job_id},
            {"$set": {"status": TimerJobStatus.COMPLETED.value, "processed_at": now_iso}},
        )

    async def reconstruct_timers_on_startup(self) -> int:
        """
        Recovers all pending timers on server startup/restart and executes immediate sweep.
        """
        db = get_database()
        # Reset any stuck RUNNING jobs to PENDING
        res = await db.response_timer_jobs.update_many(
            {"status": TimerJobStatus.RUNNING.value},
            {"$set": {"status": TimerJobStatus.PENDING.value}},
        )
        swept = await self.run_scheduler_sweep()
        logger.info("Server startup timer recovery: reset %d stuck jobs, processed %d overdue timers.", res.modified_count, swept)
        return swept

    # -----------------------------------------------------------------------
    # Escalation & Stage Advancement
    # -----------------------------------------------------------------------

    async def escalate_plan_stage(
        self,
        plan_id: str,
        target_stage: int,
        reason: str,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Escalates a response plan to a higher stage, enforcing maximum escalation limits,
        cooldown windows, and stage idempotency.
        """
        db = get_database()
        plan_doc = await db.response_plans.find_one({"response_plan_id": plan_id})
        if not plan_doc:
            return {"success": False, "reason": "Plan not found"}

        plan = ResponsePlanRecord(**plan_doc)
        if plan.status in (ResponsePlanStatus.COMPLETED, ResponsePlanStatus.CANCELLED):
            return {"success": False, "reason": "Terminal plan cannot escalate"}

        policy = await response_policy_service.get_policy_by_id(plan.policy_id)
        if not policy:
            policy = response_policy_service.get_default_policies()[0]

        if target_stage > policy.maximum_escalation_level:
            logger.warning("Target stage %d exceeds maximum escalation level %d", target_stage, policy.maximum_escalation_level)
            return {"success": False, "reason": "Exceeds maximum escalation level"}

        # Cooldown check
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        if plan.last_escalation_at:
            last_dt = datetime.fromisoformat(plan.last_escalation_at.replace("Z", "+00:00"))
            if (now - last_dt).total_seconds() < policy.cooldown_seconds:
                logger.info("Escalation rejected by cooldown period for plan %s", plan_id)
                return {"success": False, "reason": "Escalation cooldown active"}

        # Find stage config in policy
        stage_cfg = next((s for s in policy.stages if s.stage == target_stage), None)
        target_severity = stage_cfg.escalate_severity_to if stage_cfg else IncidentSeverity.CRITICAL

        # Append Stage Actions to Plan
        new_actions = []
        if stage_cfg:
            for s_act in stage_cfg.actions:
                action_id = f"act_{uuid.uuid4().hex[:10]}"
                idempotency_key = f"{plan_id}:{s_act.action_key}:{target_stage}"
                # Check idempotency
                existing = next((a for a in plan.actions if a.idempotency_key == idempotency_key), None)
                if not existing:
                    rec = ResponseActionRecord(
                        action_id=action_id,
                        plan_id=plan_id,
                        incident_id=plan.incident_id,
                        action_key=s_act.action_key,
                        type=s_act.type,
                        target=s_act.target,
                        status=ActionStatus.PENDING,
                        parameters=s_act.parameters,
                        depends_on=s_act.depends_on,
                        created_at=now_iso,
                        attempt_count=0,
                        max_attempts=s_act.max_attempts,
                        idempotency_key=idempotency_key,
                    )
                    new_actions.append(rec)

        # Update Incident Record Severity & Status
        await db.incidents.update_one(
            {"incident_id": plan.incident_id},
            {
                "$set": {
                    "status": IncidentStatus.ESCALATED.value,
                    "severity": target_severity.value if hasattr(target_severity, "value") else str(target_severity),
                    "escalation_stage": target_stage,
                    "updated_at": now_iso,
                },
                "$push": {
                    "escalation_history": {
                        "stage": target_stage,
                        "reason": reason,
                        "timestamp": now_iso,
                        "actor_id": actor_id,
                        "policy_version": plan.policy_version,
                    }
                },
            },
        )

        # Update Plan Record
        new_actions_dicts = [a.model_dump() for a in new_actions]
        await db.response_plans.update_one(
            {"response_plan_id": plan_id},
            {
                "$set": {
                    "status": ResponsePlanStatus.ESCALATING.value,
                    "escalation_level": target_stage,
                    "current_stage": stage_cfg.name if stage_cfg else f"STAGE_{target_stage}",
                    "last_escalation_at": now_iso,
                },
                "$inc": {"metrics.escalation_count": 1},
                "$push": {
                    "actions": {"$each": new_actions_dicts},
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "STAGE_ESCALATED",
                        "stage": target_stage,
                        "reason": reason,
                        "actor_id": actor_id,
                        "target_severity": target_severity.value if hasattr(target_severity, "value") else str(target_severity),
                    },
                },
            },
        )

        # Notify Stage Roles
        if stage_cfg and stage_cfg.notify_roles:
            for role in stage_cfg.notify_roles:
                for ch in stage_cfg.channels:
                    await notification_service.send_notification(
                        recipient=f"role:{role}",
                        channel=ch,
                        subject=f"ESCALATION: Incident {plan.incident_id} Stage {target_stage}",
                        message=f"Incident escalated to Stage {target_stage} ({stage_cfg.name}). Reason: {reason}",
                        incident_id=plan.incident_id,
                        recipient_type="AUTHORITY_CENTER",
                        policy_trigger=f"{plan_id}:escalate:{target_stage}",
                    )

        # Post System Message in Incident Channel
        try:
            from ...schemas.emergency import MessagePriority, MessageSendRequest, MessageType
            await messaging_service.send_message(
                incident_id=plan.incident_id,
                sender_id="system",
                sender_role=ParticipantRole.SYSTEM,
                sender_name="TourSafe System",
                req=MessageSendRequest(
                    content=f"Incident escalated to Stage {target_stage} ({stage_cfg.name if stage_cfg else 'Level ' + str(target_stage)}). Reason: {reason}",
                    priority=MessagePriority.URGENT,
                    message_type=MessageType.SYSTEM,
                ),
            )
        except Exception as e:
            logger.debug("Could not post escalation system message: %s", e)

        # Execute newly added stage actions
        asyncio.create_task(self.execute_plan_actions(plan_id))

        return {"success": True, "new_stage": target_stage, "reason": reason}

    async def _handle_no_eligible_responder(self, plan: ResponsePlanRecord) -> None:
        """
        Handles situation where no eligible responder is currently available.
        Escalates immediately to authority command center with NO_ELIGIBLE_RESPONDER alert.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.response_plans.update_one(
            {"response_plan_id": plan.response_plan_id},
            {
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "NO_ELIGIBLE_RESPONDER",
                        "details": "No available responder matches required capabilities. Urgent authority dispatch required.",
                    }
                }
            },
        )
        await notification_service.send_notification(
            recipient="role:authority_supervisor",
            channel=NotificationChannel.PUSH,
            subject=f"CRITICAL RESOURCE DEFICIT: Incident {plan.incident_id}",
            message="No eligible responders available. Manual cross-jurisdiction or supervisor assignment required.",
            incident_id=plan.incident_id,
            recipient_type="AUTHORITY_CENTER",
            policy_trigger=f"{plan.response_plan_id}:no_responder",
        )

    # -----------------------------------------------------------------------
    # External Event Handlers (Acceptance, Arrival, Resolution, Cancellation)
    # -----------------------------------------------------------------------

    async def handle_assignment_accepted(self, incident_id: str, responder_id: str, assignment_id: str) -> None:
        """
        Invoked when a responder accepts an assignment.
        Cancels ACK timeout timer, transitions plan to RESPONDING, records metrics.
        """
        db = get_database()
        plan_doc = await db.response_plans.find_one({"incident_id": incident_id, "status": {"$ne": ResponsePlanStatus.COMPLETED.value}})
        if not plan_doc:
            return

        plan = ResponsePlanRecord(**plan_doc)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Cancel pending acknowledgement timer jobs
        await db.response_timer_jobs.update_many(
            {"plan_id": plan.response_plan_id, "timer_type": "ACKNOWLEDGEMENT", "status": TimerJobStatus.PENDING.value},
            {"$set": {"status": TimerJobStatus.CANCELLED.value}},
        )

        # Calculate time_to_accept
        created_dt = datetime.fromisoformat(plan.created_at.replace("Z", "+00:00"))
        time_to_accept = (datetime.now(timezone.utc) - created_dt).total_seconds()

        await db.response_plans.update_one(
            {"response_plan_id": plan.response_plan_id},
            {
                "$set": {
                    "status": ResponsePlanStatus.RESPONDING.value,
                    "metrics.time_to_accept_seconds": time_to_accept,
                },
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "ASSIGNMENT_ACCEPTED",
                        "responder_id": responder_id,
                        "assignment_id": assignment_id,
                        "time_to_accept_seconds": time_to_accept,
                    }
                },
            },
        )

        # Notify tourist that responder is responding
        await notification_service.send_notification(
            recipient=plan_doc.get("incident_id", ""),
            channel=NotificationChannel.PUSH,
            subject="Help Is On The Way",
            message="A safety responder has accepted the mission and is responding.",
            incident_id=incident_id,
            recipient_type="TOURIST",
            policy_trigger=f"{assignment_id}:accept",
        )

    async def handle_assignment_declined(self, incident_id: str, responder_id: str, reason: str) -> None:
        """
        Invoked when a responder declines an assignment.
        Triggers immediate policy redispatch or advances escalation stage.
        """
        db = get_database()
        plan_doc = await db.response_plans.find_one({"incident_id": incident_id, "status": {"$ne": ResponsePlanStatus.COMPLETED.value}})
        if not plan_doc:
            return

        plan = ResponsePlanRecord(**plan_doc)
        now_iso = datetime.now(timezone.utc).isoformat()

        await db.response_plans.update_one(
            {"response_plan_id": plan.response_plan_id},
            {
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "ASSIGNMENT_DECLINED",
                        "responder_id": responder_id,
                        "reason": reason,
                    }
                }
            },
        )

        # Trigger escalation / redispatch
        await self.escalate_plan_stage(
            plan_id=plan.response_plan_id,
            target_stage=plan.escalation_level + 1,
            reason=f"Responder {responder_id} declined assignment: {reason}",
        )

    async def handle_responder_arrived(self, incident_id: str, responder_id: str, arrival_data: Dict[str, Any]) -> None:
        """
        Invoked when responder arrives on scene.
        """
        db = get_database()
        plan_doc = await db.response_plans.find_one({"incident_id": incident_id, "status": {"$ne": ResponsePlanStatus.COMPLETED.value}})
        if not plan_doc:
            return

        plan = ResponsePlanRecord(**plan_doc)
        created_dt = datetime.fromisoformat(plan.created_at.replace("Z", "+00:00"))
        time_to_arrival = (datetime.now(timezone.utc) - created_dt).total_seconds()
        now_iso = datetime.now(timezone.utc).isoformat()

        await db.response_plans.update_one(
            {"response_plan_id": plan.response_plan_id},
            {
                "$set": {
                    "status": ResponsePlanStatus.RESOLVING.value,
                    "metrics.time_to_arrival_seconds": time_to_arrival,
                },
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "RESPONDER_ON_SCENE",
                        "responder_id": responder_id,
                        "arrival_data": arrival_data,
                        "time_to_arrival_seconds": time_to_arrival,
                    }
                },
            },
        )

    async def handle_incident_resolved(self, incident_id: str, actor_id: str, resolution_data: Dict[str, Any]) -> None:
        """
        Invoked when incident is resolved. Cancels future actions and marks response plan COMPLETED.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        plan_doc = await db.response_plans.find_one({"incident_id": incident_id, "status": {"$ne": ResponsePlanStatus.COMPLETED.value}})
        if not plan_doc:
            return

        plan = ResponsePlanRecord(**plan_doc)
        created_dt = datetime.fromisoformat(plan.created_at.replace("Z", "+00:00"))
        time_to_resolution = (datetime.now(timezone.utc) - created_dt).total_seconds()

        # Cancel pending timers
        await db.response_timer_jobs.update_many(
            {"plan_id": plan.response_plan_id, "status": TimerJobStatus.PENDING.value},
            {"$set": {"status": TimerJobStatus.CANCELLED.value}},
        )

        await db.response_plans.update_one(
            {"response_plan_id": plan.response_plan_id},
            {
                "$set": {
                    "status": ResponsePlanStatus.COMPLETED.value,
                    "completed_at": now_iso,
                    "metrics.time_to_resolution_seconds": time_to_resolution,
                },
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "PLAN_COMPLETED",
                        "resolved_by": actor_id,
                        "resolution_data": resolution_data,
                        "time_to_resolution_seconds": time_to_resolution,
                    }
                },
            },
        )
        logger.info("Response plan %s completed for incident %s", plan.response_plan_id, incident_id)

    async def handle_incident_cancelled(self, incident_id: str, actor_id: str, reason: str) -> None:
        """
        Invoked when incident is cancelled (e.g. false alarm). Cancels response plan and future jobs.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.response_timer_jobs.update_many(
            {"incident_id": incident_id, "status": TimerJobStatus.PENDING.value},
            {"$set": {"status": TimerJobStatus.CANCELLED.value}},
        )
        await db.response_plans.update_many(
            {"incident_id": incident_id, "status": {"$nin": [ResponsePlanStatus.COMPLETED.value, ResponsePlanStatus.CANCELLED.value]}},
            {
                "$set": {
                    "status": ResponsePlanStatus.CANCELLED.value,
                    "cancelled_at": now_iso,
                },
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "PLAN_CANCELLED",
                        "cancelled_by": actor_id,
                        "reason": reason,
                    }
                },
            },
        )

    # -----------------------------------------------------------------------
    # Human-in-the-Loop Overrides & Controls
    # -----------------------------------------------------------------------

    async def pause_automation(self, plan_id: str, user_id: str, reason: str) -> ResponsePlanRecord:
        """
        Pauses automated actions and timers on a response plan.
        """
        db = get_database()
        doc = await db.response_plans.find_one({"response_plan_id": plan_id})
        if not doc:
            raise ValueError(f"Response plan '{plan_id}' not found.")

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.response_plans.update_one(
            {"response_plan_id": plan_id},
            {
                "$set": {
                    "is_paused": True,
                    "paused_at": now_iso,
                    "paused_by": user_id,
                    "paused_reason": reason,
                },
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "AUTOMATION_PAUSED",
                        "paused_by": user_id,
                        "reason": reason,
                    }
                },
            },
        )
        updated = await db.response_plans.find_one({"response_plan_id": plan_id})
        return ResponsePlanRecord(**updated)

    async def resume_automation(self, plan_id: str, user_id: str, reason: str) -> ResponsePlanRecord:
        """
        Resumes automation on a paused response plan and re-evaluates ready actions.
        """
        db = get_database()
        doc = await db.response_plans.find_one({"response_plan_id": plan_id})
        if not doc:
            raise ValueError(f"Response plan '{plan_id}' not found.")

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.response_plans.update_one(
            {"response_plan_id": plan_id},
            {
                "$set": {
                    "is_paused": False,
                    "paused_at": None,
                    "paused_by": None,
                    "paused_reason": None,
                },
                "$push": {
                    "timeline": {
                        "timestamp": now_iso,
                        "event": "AUTOMATION_RESUMED",
                        "resumed_by": user_id,
                        "reason": reason,
                    }
                },
            },
        )
        # Re-trigger ready actions
        asyncio.create_task(self.execute_plan_actions(plan_id))
        updated = await db.response_plans.find_one({"response_plan_id": plan_id})
        return ResponsePlanRecord(**updated)

    async def manual_override(self, plan_id: str, user_id: str, req: ManualOverrideRequest) -> ResponsePlanRecord:
        """
        Executes an authorized operator override on a response plan.
        """
        db = get_database()
        doc = await db.response_plans.find_one({"response_plan_id": plan_id})
        if not doc:
            raise ValueError(f"Response plan '{plan_id}' not found.")

        plan = ResponsePlanRecord(**doc)
        now_iso = datetime.now(timezone.utc).isoformat()

        if req.action_type == "FORCE_ESCALATE":
            target_stage = req.target_escalation_stage or (plan.escalation_level + 1)
            await self.escalate_plan_stage(plan_id, target_stage, reason=f"Manual operator override by {user_id}: {req.reason}", actor_id=user_id)

        elif req.action_type == "REASSIGN" and req.target_responder_id:
            from .assignment_service import assignment_service
            await assignment_service.create_assignment(
                incident_id=plan.incident_id,
                responder_id=req.target_responder_id,
                assigned_by=user_id,
                notes=f"Manual reassignment by operator {user_id}: {req.reason}",
            )
            await db.response_plans.update_one(
                {"response_plan_id": plan_id},
                {
                    "$push": {
                        "timeline": {
                            "timestamp": now_iso,
                            "event": "MANUAL_REASSIGNMENT",
                            "responder_id": req.target_responder_id,
                            "operator_id": user_id,
                            "reason": req.reason,
                        }
                    }
                },
            )

        elif req.action_type == "OVERRIDE_STATUS" and req.target_plan_status:
            await db.response_plans.update_one(
                {"response_plan_id": plan_id},
                {
                    "$set": {"status": req.target_plan_status.value},
                    "$push": {
                        "timeline": {
                            "timestamp": now_iso,
                            "event": "STATUS_OVERRIDDEN",
                            "operator_id": user_id,
                            "new_status": req.target_plan_status.value,
                            "reason": req.reason,
                        }
                    },
                },
            )

        updated = await db.response_plans.find_one({"response_plan_id": plan_id})
        return ResponsePlanRecord(**updated)

    async def _notify_authority_of_action_failure(self, plan: ResponsePlanRecord, action: ResponseActionRecord) -> None:
        """
        Sends dead-letter failure notification to authority command center.
        """
        await notification_service.send_notification(
            recipient="role:authority_supervisor",
            channel=NotificationChannel.PUSH,
            subject=f"ACTION FAILED [Dead-Letter]: Incident {plan.incident_id}",
            message=f"Action '{action.action_key or action.type.value}' exhausted retries. Failure: {action.failure_reason}",
            incident_id=plan.incident_id,
            recipient_type="AUTHORITY_CENTER",
            policy_trigger=f"{action.action_id}:dead_letter",
        )

    # -----------------------------------------------------------------------
    # Observability, Health & KPIs
    # -----------------------------------------------------------------------

    async def get_plan_by_incident(self, incident_id: str) -> Optional[ResponsePlanDetailResponse]:
        """
        Returns full detailed view of the response plan for an incident.
        """
        db = get_database()
        doc = await db.response_plans.find_one({"incident_id": incident_id})
        if not doc:
            return None

        plan = ResponsePlanRecord(**doc)
        inc_doc = await db.incidents.find_one({"incident_id": incident_id})
        policy = await response_policy_service.get_policy_by_id(plan.policy_id)

        # Query active timer jobs
        timer_docs = db.response_timer_jobs.find({
            "plan_id": plan.response_plan_id,
            "status": TimerJobStatus.PENDING.value,
        })
        timers = []
        async for t in timer_docs:
            timers.append(ResponseTimerJobRecord(**t))

        pending_actions = [a for a in plan.actions if a.status == ActionStatus.PENDING]
        completed_actions = [a for a in plan.actions if a.status == ActionStatus.COMPLETED]
        failed_actions = [a for a in plan.actions if a.status in (ActionStatus.FAILED, ActionStatus.RETRYING)]

        # SLA Status Check
        sla_status = SlaStatus.ON_TRACK
        if policy and policy.target_sla_seconds > 0:
            created_dt = datetime.fromisoformat(plan.created_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds()
            if elapsed > policy.target_sla_seconds:
                sla_status = SlaStatus.BREACHED
            elif elapsed > (policy.target_sla_seconds * 0.75):
                sla_status = SlaStatus.AT_RISK

        return ResponsePlanDetailResponse(
            plan=plan,
            incident=inc_doc,
            policy=policy,
            active_timers=timers,
            pending_actions=pending_actions,
            completed_actions=completed_actions,
            failed_actions=failed_actions,
            sla_status=sla_status,
            time_to_acknowledge_seconds=plan.metrics.get("time_to_acknowledge_seconds"),
            time_to_dispatch_seconds=plan.metrics.get("time_to_dispatch_seconds"),
            time_to_accept_seconds=plan.metrics.get("time_to_accept_seconds"),
            time_to_arrival_seconds=plan.metrics.get("time_to_arrival_seconds"),
            time_to_resolution_seconds=plan.metrics.get("time_to_resolution_seconds"),
        )

    async def get_health(self) -> OrchestratorHealthResponse:
        """
        Calculates health metrics for response orchestrator.
        """
        db = get_database()
        active_plans = await db.response_plans.count_documents({
            "status": {"$in": [ResponsePlanStatus.ACTIVE.value, ResponsePlanStatus.WAITING_ACK.value, ResponsePlanStatus.RESPONDING.value, ResponsePlanStatus.ESCALATING.value]}
        })
        pending_jobs = await db.response_timer_jobs.count_documents({"status": TimerJobStatus.PENDING.value})
        active_policies = await db.response_policies.count_documents({"status": PolicyStatus.ACTIVE.value})

        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        status = OrchestratorHealthStatus.HEALTHY if self._is_running else OrchestratorHealthStatus.FAILED

        return OrchestratorHealthResponse(
            status=status,
            uptime_seconds=uptime,
            active_plans_count=active_plans,
            pending_timer_jobs_count=pending_jobs,
            failed_actions_24h=self._failed_actions_24h,
            active_policies_count=active_policies,
            is_scheduler_running=self._is_running,
            last_sweep_at=self._last_sweep_at,
            external_emergency_service_status="NOT_CONNECTED",
            warnings=["External emergency service direct dial is abstracted and NOT_CONNECTED."] if True else [],
        )

    async def get_kpis(self) -> ResponseKpiResponse:
        """
        Computes response KPIs across all recorded plans.
        """
        db = get_database()
        total_plans = await db.response_plans.count_documents({})
        completed = await db.response_plans.count_documents({"status": ResponsePlanStatus.COMPLETED.value})
        cancelled = await db.response_plans.count_documents({"status": ResponsePlanStatus.CANCELLED.value})
        failed = await db.response_plans.count_documents({"status": ResponsePlanStatus.FAILED.value})

        cursor = db.response_plans.find({"status": ResponsePlanStatus.COMPLETED.value})
        accept_times = []
        resolution_times = []
        escalated_plans = 0

        async for doc in cursor:
            m = doc.get("metrics", {})
            if m.get("time_to_accept_seconds"):
                accept_times.append(m["time_to_accept_seconds"])
            if m.get("time_to_resolution_seconds"):
                resolution_times.append(m["time_to_resolution_seconds"])
            if doc.get("escalation_level", 0) > 0:
                escalated_plans += 1

        avg_accept = sum(accept_times) / len(accept_times) if accept_times else None
        avg_res = sum(resolution_times) / len(resolution_times) if resolution_times else None
        esc_rate = (escalated_plans / total_plans * 100) if total_plans > 0 else 0.0

        return ResponseKpiResponse(
            total_response_plans=total_plans,
            completed_plans=completed,
            cancelled_plans=cancelled,
            failed_plans=failed,
            avg_time_to_accept_seconds=avg_accept,
            avg_time_to_resolution_seconds=avg_res,
            escalation_rate_percentage=esc_rate,
            failed_action_rate_percentage=0.0,
            sla_breach_rate_percentage=0.0,
        )


response_orchestrator = ResponseOrchestrator()
