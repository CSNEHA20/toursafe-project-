import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ZoneType(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    RESTRICTED = "restricted"


class ZoneRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ZoneStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class ZoneAuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    BOUNDARY_UPDATED = "boundary_updated"
    STATUS_CHANGED = "status_changed"
    DELETED = "deleted"


class GeoJSONPointModel(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]

    model_config = {"populate_by_name": True}


class GeoJSONPolygonModel(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]  # list of linear rings: [[[lon, lat], ...]]

    model_config = {"populate_by_name": True}


class GeoJSONMultiPolygonModel(BaseModel):
    type: str = "MultiPolygon"
    coordinates: List[List[List[List[float]]]]

    model_config = {"populate_by_name": True}


class Zone(BaseModel):
    """
    Persistent MongoDB Model for Geospatial Safety Zones.
    Stores RFC 7946 GeoJSON boundaries indexed by 2dsphere.
    """
    id: str = Field(default_factory=lambda: f"zone_{uuid.uuid4().hex[:12]}")
    zone_id: Optional[str] = None  # Alias / canonical reference matching id
    name: str
    description: str = ""
    zone_type: ZoneType = ZoneType.SAFE
    risk_level: ZoneRiskLevel = ZoneRiskLevel.LOW
    status: ZoneStatus = ZoneStatus.ACTIVE
    boundary: Dict[str, Any]  # GeoJSON Polygon / MultiPolygon
    center: Dict[str, Any]    # GeoJSON Point [longitude, latitude]
    properties: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "use_enum_values": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

    def __init__(self, **data: Any):
        if "id" not in data and "zone_id" in data:
            data["id"] = data["zone_id"]
        elif "zone_id" not in data and "id" in data:
            data["zone_id"] = data["id"]
        super().__init__(**data)
        if not self.zone_id:
            self.zone_id = self.id

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Format for MongoDB persistence."""
        return {
            "id": self.id,
            "zone_id": self.zone_id or self.id,
            "name": self.name,
            "description": self.description,
            "zone_type": self.zone_type if isinstance(self.zone_type, str) else self.zone_type.value,
            "risk_level": self.risk_level if isinstance(self.risk_level, str) else self.risk_level.value,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "boundary": self.boundary,
            "center": self.center,
            "properties": self.properties,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mongo_dict(cls, data: Dict[str, Any]) -> "Zone":
        """Instantiate Zone from MongoDB document."""
        zone_id = data.get("zone_id") or data.get("id") or str(data.get("_id", ""))
        return cls(
            id=zone_id,
            zone_id=zone_id,
            name=data.get("name", ""),
            description=data.get("description", ""),
            zone_type=data.get("zone_type", ZoneType.SAFE),
            risk_level=data.get("risk_level", ZoneRiskLevel.LOW),
            status=data.get("status", ZoneStatus.ACTIVE),
            boundary=data.get("boundary", {}),
            center=data.get("center", {}),
            properties=data.get("properties", {}),
            is_active=data.get("is_active", True),
            created_by=data.get("created_by"),
            updated_by=data.get("updated_by"),
            created_at=data.get("created_at") or datetime.now(timezone.utc),
            updated_at=data.get("updated_at") or datetime.now(timezone.utc),
        )


class ZoneAudit(BaseModel):
    """
    Immutable Audit Record for Zone Modifications.
    """
    id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    audit_id: Optional[str] = None
    zone_id: str
    action: ZoneAuditAction
    changed_by: str
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    change_summary: Optional[str] = None

    model_config = {
        "use_enum_values": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

    def __init__(self, **data: Any):
        if "id" not in data and "audit_id" in data:
            data["id"] = data["audit_id"]
        elif "audit_id" not in data and "id" in data:
            data["audit_id"] = data["id"]
        super().__init__(**data)
        if not self.audit_id:
            self.audit_id = self.id

    def to_mongo_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "audit_id": self.audit_id or self.id,
            "zone_id": self.zone_id,
            "action": self.action if isinstance(self.action, str) else self.action.value,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at,
            "previous_values": self.previous_values,
            "new_values": self.new_values,
            "change_summary": self.change_summary,
        }

    @classmethod
    def from_mongo_dict(cls, data: Dict[str, Any]) -> "ZoneAudit":
        audit_id = data.get("audit_id") or data.get("id") or str(data.get("_id", ""))
        return cls(
            id=audit_id,
            audit_id=audit_id,
            zone_id=data.get("zone_id", ""),
            action=data.get("action", ZoneAuditAction.UPDATED),
            changed_by=data.get("changed_by", "system"),
            changed_at=data.get("changed_at") or datetime.now(timezone.utc),
            previous_values=data.get("previous_values"),
            new_values=data.get("new_values"),
            change_summary=data.get("change_summary"),
        )
