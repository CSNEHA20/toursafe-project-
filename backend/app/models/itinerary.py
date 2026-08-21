import uuid
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import Field
from .user import TimeStampedModel


class Itinerary(TimeStampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tourist_id: str  # references Tourist.id
    title: str
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    status: str = "active"  # "active", "completed", "cancelled"
    entries: Optional[List[dict]] = Field(default_factory=list)

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "Itinerary":
        entries = data.get("entries", [])
        return Itinerary(
            id=data.get("id", ""),
            tourist_id=data["tourist_id"],
            title=data["title"],
            destination=data.get("destination"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            notes=data.get("notes"),
            status=data.get("status", "active"),
            entries=entries,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tourist_id": self.tourist_id,
            "title": self.title,
            "destination": self.destination,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "notes": self.notes,
            "status": self.status,
            "entries": self.entries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }