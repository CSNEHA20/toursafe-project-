import uuid
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import Field
from .user import TimeStampedModel


class Tourist(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # references User.id
    full_name: str
    email: str
    phone: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None  # "male", "female", "other"
    passport_number: Optional[str] = None
    profile_photo_url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    kyc_status: str = "pending"  # "pending", "submitted", "verified", "rejected"
    identity_document_type: Optional[str] = None  # "passport", "aadhaar", "driver_license", etc.
    identity_document_reference: Optional[str] = None
    identity_verified_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "Tourist":
        return Tourist(
            id=data.get("id", ""),
            user_id=data["user_id"],
            full_name=data["full_name"],
            email=data["email"],
            phone=data.get("phone"),
            nationality=data.get("nationality"),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            passport_number=data.get("passport_number"),
            profile_photo_url=data.get("profile_photo_url"),
            address=data.get("address"),
            city=data.get("city"),
            country=data.get("country"),
            kyc_status=data.get("kyc_status", "pending"),
            identity_document_type=data.get("identity_document_type"),
            identity_document_reference=data.get("identity_document_reference"),
            identity_verified_at=data.get("identity_verified_at"),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "nationality": self.nationality,
            "date_of_birth": self.date_of_birth,
            "gender": self.gender,
            "passport_number": self.passport_number,
            "profile_photo_url": self.profile_photo_url,
            "address": self.address,
            "city": self.city,
            "country": self.country,
            "kyc_status": self.kyc_status,
            "identity_document_type": self.identity_document_type,
            "identity_document_reference": self.identity_document_reference,
            "identity_verified_at": self.identity_verified_at,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }