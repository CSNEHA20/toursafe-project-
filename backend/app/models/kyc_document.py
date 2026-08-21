import uuid
from typing import Optional
from datetime import datetime, timezone
from pydantic import Field
from .user import TimeStampedModel


class KYCDocument(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tourist_id: str  # references Tourist.id
    document_type: str  # "passport", "aadhaar", "driver_license", "national_id"
    document_reference: str  # document number/file reference
    status: str = "pending"  # "pending", "submitted", "verified", "rejected"
    submitted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "KYCDocument":
        return KYCDocument(
            id=data.get("id", ""),
            tourist_id=data["tourist_id"],
            document_type=data["document_type"],
            document_reference=data["document_reference"],
            status=data.get("status", "pending"),
            submitted_at=data.get("submitted_at"),
            verified_at=data.get("verified_at"),
            rejection_reason=data.get("rejection_reason"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tourist_id": self.tourist_id,
            "document_type": self.document_type,
            "document_reference": self.document_reference,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "verified_at": self.verified_at,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }