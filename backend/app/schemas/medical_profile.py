from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MedicalProfileCreate(BaseModel):
    tourist_id: str
    blood_group: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    medical_conditions: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    disability_information: Optional[str] = None
    other_emergency_medical_notes: Optional[str] = None


class MedicalProfileUpdate(BaseModel):
    blood_group: Optional[str] = None
    allergies: Optional[List[str]] = None
    medical_conditions: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    disability_information: Optional[str] = None
    other_emergency_medical_notes: Optional[str] = None


class MedicalProfileResponse(BaseModel):
    id: str
    tourist_id: str
    blood_group: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    medical_conditions: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    disability_information: Optional[str] = None
    other_emergency_medical_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


class MedicalProfileList(BaseModel):
    items: List[MedicalProfileResponse]
    total: int
    page: int
    per_page: int