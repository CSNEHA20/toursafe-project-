import uuid
from typing import Optional
from datetime import datetime, timezone
from pydantic import Field
from .user import TimeStampedModel


class Authority(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # references User.id
    full_name: str
    organization_name: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    office_phone: Optional[str] = None
    address: Optional[str] = None
    license_number: Optional[str] = None
    verification_status: str = "pending"  # "pending", "verified", "rejected"
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "Authority":
        return Authority(
            id=data.get("id", ""),
            user_id=data["user_id"],
            full_name=data["full_name"],
            organization_name=data.get("organization_name"),
            designation=data.get("designation"),
            phone=data.get("phone"),
            office_phone=data.get("office_phone"),
            address=data.get("address"),
            license_number=data.get("license_number"),
            verification_status=data.get("verification_status", "pending"),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "organization_name": self.organization_name,
            "designation": self.designation,
            "phone": self.phone,
            "office_phone": self.office_phone,
            "address": self.address,
            "license_number": self.license_number,
            "verification_status": self.verification_status,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }