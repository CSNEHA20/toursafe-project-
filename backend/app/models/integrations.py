from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntegrationModel(BaseModel):
    id: str = Field(..., alias="_id")
    integration_id: str
    provider_name: str
    integration_type: str
    status: str = "ACTIVE"
    environment: str = "DEVELOPMENT"
    is_real_provider: bool = False
    capabilities: List[str] = Field(default_factory=list)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    health: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    class Config:
        populate_by_name = True


class IntegrationAuditModel(BaseModel):
    id: str = Field(..., alias="_id")
    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str
    integration_id: Optional[str] = None
    provider_name: Optional[str] = None
    integration_type: Optional[str] = None
    actor_id: str
    actor_role: str
    correlation_id: str
    status: str
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class DeadLetterModel(BaseModel):
    id: str = Field(..., alias="_id")
    record_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operation_name: str
    integration_id: str
    provider_name: str
    integration_type: str
    idempotency_key: str
    correlation_id: str
    attempt_count: int = 1
    max_attempts: int = 3
    error_code: str
    error_message: str
    payload_summary: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None

    class Config:
        populate_by_name = True


class ExternalIncidentMappingModel(BaseModel):
    id: str = Field(..., alias="_id")
    toursafe_incident_id: str
    external_system: str
    external_incident_id: str
    toursafe_status: str
    external_status: str
    last_synced_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sync_status: str = "IN_SYNC"  # IN_SYNC, CONFLICT, FAILED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
