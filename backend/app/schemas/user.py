from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    phone: Optional[str] = None
    role: str = "tourist"

    model_config = {"use_enum_values": True}


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    model_config = {"use_enum_values": True}


class TokenRefresh(BaseModel):
    refresh_token: str

    model_config = {"use_enum_values": True}


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    full_name: Optional[str] = None

    model_config = {"use_enum_values": True, "from_attributes": True}


class TouristRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    phone: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    passport_number: Optional[str] = None

    model_config = {"use_enum_values": True}


class TouristProfile(BaseModel):
    id: str
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    passport_number: Optional[str] = None
    profile_photo_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


class AuthorityRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    organization_name: str
    designation: Optional[str] = None
    phone: Optional[str] = None
    office_phone: Optional[str] = None
    address: Optional[str] = None
    license_number: Optional[str] = None

    model_config = {"use_enum_values": True}


class AuthorityProfile(BaseModel):
    id: str
    user_id: str
    full_name: str
    organization_name: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    office_phone: Optional[str] = None
    address: Optional[str] = None
    license_number: Optional[str] = None
    verification_status: str = "pending"

    model_config = {"use_enum_values": True, "from_attributes": True}


class VerificationUpdate(BaseModel):
    verification_status: str  # "verified" or "rejected"


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class HealthCheck(BaseModel):
    status: str
    service: str
    timestamp: datetime
    mongodb: str

    model_config = {"use_enum_values": True}