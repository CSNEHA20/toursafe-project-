import uuid
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import Field
from .user import TimeStampedModel


class MedicalProfile(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tourist_id: str  # references Tourist.id
    blood_group: Optional[str] = None  # e.g., "A+", "B-", "O+", "O-", "AB+", "AB-"
    allergies: List[str] = Field(default_factory=list)
    medical_conditions: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    disability_information: Optional[str] = None
    other_emergency_medical_notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "MedicalProfile":
        return MedicalProfile(
            id=data.get("id", ""),
            tourist_id=data["tourist_id"],
            blood_group=data.get("blood_group"),
            allergies=data.get("allergies", []),
            medical_conditions=data.get("medical_conditions", []),
            medications=data.get("medications", []),
            disability_information=data.get("disability_information"),
            other_emergency_medical_notes=data.get("other_emergency_medical_notes"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tourist_id": self.tourist_id,
            "blood_group": self.blood_group,
            "allergies": self.allergies,
            "medical_conditions": self.medical_conditions,
            "medications": self.medications,
            "disability_information": self.disability_information,
            "other_emergency_medical_notes": self.other_emergency_medical_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }