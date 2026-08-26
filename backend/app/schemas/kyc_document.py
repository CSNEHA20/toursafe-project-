from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class KYCDocumentCreate(BaseModel):
    tourist_id: str
    document_type: str  # "passport", "aadhaar", "driver_license", "national_id"
    document_reference: str  # document number/file reference

    model_config = {"use_enum_values": True}


class KYCDocumentUpdate(BaseModel):
    status: str  # "pending", "submitted", "verified", "rejected"
    rejection_reason: Optional[str] = None


class KYCDocumentResponse(BaseModel):
    id: str
    tourist_id: str
    document_type: str
    document_reference: str
    status: str
    submitted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


class KYCDocumentList(BaseModel):
    items: List[KYCDocumentResponse]
    total: int
    page: int
    per_page: int