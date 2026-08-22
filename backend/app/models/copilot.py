"""
TourSafe Authority AI Copilot Models.
Defines schema and storage contracts for sessions, messages, tool traces,
auditing, knowledge base (RAG), and human-in-the-loop action proposals.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"
    SYSTEM = "SYSTEM"


class CopilotSessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ActionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class FeedbackRating(str, Enum):
    HELPFUL = "HELPFUL"
    NOT_HELPFUL = "NOT_HELPFUL"
    INCORRECT = "INCORRECT"
    OUTDATED = "OUTDATED"


class ToolCallRecord(BaseModel):
    call_id: str = Field(default_factory=lambda: f"call_{uuid4().hex[:8]}")
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolResultRecord(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    source: str
    observed_at: Optional[str] = None
    latency_ms: float = 0.0


class CitationSource(BaseModel):
    source_type: str  # "data_source" | "document" | "incident" | "zone" | "policy"
    title: str
    identifier: Optional[str] = None
    version: Optional[str] = None
    section: Optional[str] = None
    freshness: Optional[str] = None
    snippet: Optional[str] = None


class ActionProposal(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act_{uuid4().hex[:12]}")
    session_id: str
    user_id: str
    organization_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    tool_name: str
    action_type: str  # "dispatch_responder" | "escalate_incident" | "pause_response_plan" | "notify_authority"
    target_id: str
    target_description: str
    reason: str
    policy_reference: Optional[str] = None
    expected_effect: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confirmation_token: str
    idempotency_key: str
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    execution_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["created_at"] = self.created_at.isoformat()
        d["expires_at"] = self.expires_at.isoformat()
        if self.confirmed_at:
            d["confirmed_at"] = self.confirmed_at.isoformat()
        return d


class CopilotMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    session_id: str
    role: MessageRole
    content: str
    citations: List[CitationSource] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    tool_results: List[ToolResultRecord] = Field(default_factory=list)
    action_proposal: Optional[ActionProposal] = None
    data_freshness: Optional[str] = None
    uncertainty_note: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0.0
    model: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["timestamp"] = self.timestamp.isoformat()
        return d


class CopilotSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"ses_{uuid4().hex[:12]}")
    user_id: str
    organization_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    title: str = "Authority Operations Assistance"
    status: CopilotSessionStatus = CopilotSessionStatus.ACTIVE
    context_summary: Optional[str] = None
    active_incident_id: Optional[str] = None
    active_zone_id: Optional[str] = None
    active_responder_id: Optional[str] = None
    message_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d


class CopilotAuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"cop_aud_{uuid4().hex[:12]}")
    user_id: str
    session_id: str
    role: str
    action: str  # "query", "tool_executed", "action_proposed", "action_confirmed", "action_cancelled", "rag_retrieved", "feedback_submitted"
    tool_name: Optional[str] = None
    input_params: Optional[Dict[str, Any]] = None
    result_summary: Optional[str] = None
    authorization_passed: bool = True
    jurisdiction_id: Optional[str] = None
    confirmation_token: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["timestamp"] = self.timestamp.isoformat()
        return d


class CopilotFeedback(BaseModel):
    feedback_id: str = Field(default_factory=lambda: f"fb_{uuid4().hex[:12]}")
    message_id: str
    session_id: str
    user_id: str
    rating: FeedbackRating
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["timestamp"] = self.timestamp.isoformat()
        return d


class KnowledgeDocument(BaseModel):
    document_id: str = Field(default_factory=lambda: f"doc_{uuid4().hex[:12]}")
    title: str
    category: str  # "sop", "policy", "protocol", "manual", "technical"
    version: str = "v1.0.0"
    jurisdiction_id: Optional[str] = None  # None = Global / Universal
    status: str = "active"  # "active" | "retired" | "draft"
    effective_date: str = "2026-01-01"
    sections: List[Dict[str, str]] = Field(default_factory=list)  # [{"heading": "...", "content": "..."}]
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d
