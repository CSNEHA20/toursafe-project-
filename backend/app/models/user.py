import uuid
from pymongo import IndexModel, ASCENDING, DESCENDING
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, timezone


class TimeStampedModel(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True}


class User(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    password_hash: str
    role: str  # "tourist", "authority", "admin", "responder"
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    last_login_at: Optional[datetime] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "User":
        return User(
            id=data.get("id", ""),
            email=data["email"],
            password_hash=data["password_hash"],
            role=data["role"],
            full_name=data.get("full_name"),
            phone=data.get("phone"),
            is_active=data.get("is_active", True),
            is_verified=data.get("is_verified", False),
            last_login_at=data.get("last_login_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "password_hash": self.password_hash,
            "role": self.role,
            "full_name": self.full_name,
            "phone": self.phone,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "last_login_at": self.last_login_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Tourist(TimeStampedModel):
    id: str
    user_id: str  # references User.id
    full_name: str
    email: str
    phone: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None  # "male", "female", "other"
    passport_number: Optional[str] = None
    profile_photo_url: Optional[str] = None
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
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Authority(TimeStampedModel):
    id: str
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