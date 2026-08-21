from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EmergencyContactCreate(BaseModel):
    tourist_id: str
    name: str
    relationship: str
    phone: str
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    priority: int = 1


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    priority: Optional[int] = None


class EmergencyContactResponse(BaseModel):
    id: str
    tourist_id: str
    name: str
    relationship: str
    phone: str
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    priority: int
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


class EmergencyContactList(BaseModel):
    items: List[EmergencyContactResponse]
    total: int
    page: int
    per_page: int