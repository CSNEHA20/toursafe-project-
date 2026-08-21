import uuid
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import Field
from .user import TimeStampedModel


class EmergencyContact(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tourist_id: str  # references Tourist.id
    name: str
    relationship: str
    phone: str
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    priority: int = 1  # 1 = primary, 2 = secondary, etc. Unique per tourist
    is_primary: bool = False

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "EmergencyContact":
        return EmergencyContact(
            id=data.get("id", ""),
            tourist_id=data["tourist_id"],
            name=data["name"],
            relationship=data["relationship"],
            phone=data["phone"],
            alternate_phone=data.get("alternate_phone"),
            email=data.get("email"),
            priority=data.get("priority", 1),
            is_primary=data.get("is_primary", False),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tourist_id": self.tourist_id,
            "name": self.name,
            "relationship": self.relationship,
            "phone": self.phone,
            "alternate_phone": self.alternate_phone,
            "email": self.email,
            "priority": self.priority,
            "is_primary": self.is_primary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }