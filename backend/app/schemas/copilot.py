"""
TourSafe Authority AI Copilot Schemas.
Defines Pydantic request and response schemas for Copilot sessions, messages,
tool schemas, action previews, human confirmations, and feedback.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..models.copilot import (
    ActionProposal,
    ActionStatus,
    CitationSource,
    CopilotSessionStatus,
    FeedbackRating,
    MessageRole,
    ToolCallRecord,
    ToolResultRecord,
)


class CopilotSessionCreate(BaseModel):
    title: Optional[str] = Field(default="Authority Operational Assistance")
    active_incident_id: Optional[str] = None
    active_zone_id: Optional[str] = None
    active_responder_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CopilotSessionResponse(BaseModel):
    session_id: str
    user_id: str
    organization_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    title: str
    status: CopilotSessionStatus
    context_summary: Optional[str] = None
    active_incident_id: Optional[str] = None
    active_zone_id: Optional[str] = None
    active_responder_id: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CopilotMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, description="Natural language question or command")
    active_incident_id: Optional[str] = None
    active_zone_id: Optional[str] = None
    active_responder_id: Optional[str] = None
    stream: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CopilotMessageResponse(BaseModel):
    message_id: str
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
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionConfirmRequest(BaseModel):
    confirmation_token: str = Field(..., description="Cryptographically signed or server-generated confirmation token")
    idempotency_key: Optional[str] = None
    reason_note: Optional[str] = None


class ActionCancelRequest(BaseModel):
    reason_note: Optional[str] = None


class ActionResponse(BaseModel):
    action_id: str
    session_id: str
    tool_name: str
    action_type: str
    target_id: str
    status: ActionStatus
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    execution_result: Optional[Dict[str, Any]] = None
    message: str


class FeedbackCreate(BaseModel):
    rating: FeedbackRating
    reason: Optional[str] = None


class ToolDefinitionSchema(BaseModel):
    name: str
    category: str
    description: str
    parameters: Dict[str, Any]
    required_role: List[str]
    read_only: bool = True
    requires_preview: bool = False


class CopilotMetricsResponse(BaseModel):
    total_sessions: int
    total_messages: int
    total_tool_calls: int
    total_actions_proposed: int
    total_actions_confirmed: int
    feedback_breakdown: Dict[str, int]
    avg_latency_ms: float
    total_tokens_used: int
    tools_usage_count: Dict[str, int]
