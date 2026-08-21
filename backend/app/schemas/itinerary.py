from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ItineraryEntry(BaseModel):
    id: Optional[str] = None
    spot_name: str
    address: Optional[str] = None
    stop_type: Optional[str] = "other"
    planned_arrival: Optional[str] = None
    planned_departure: Optional[str] = None
    expected_duration_hours: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class ItineraryCreate(BaseModel):
    title: str
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    stops: List[ItineraryEntry] = Field(default_factory=list)


class ItineraryUpdate(BaseModel):
    title: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ItineraryResponse(BaseModel):
    id: str
    tourist_id: str
    title: str
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


class ItineraryList(BaseModel):
    items: List[ItineraryResponse]
    total: int
    page: int
    per_page: int