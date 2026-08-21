from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from ..models.zone import ZoneType, ZoneRiskLevel, ZoneStatus, ZoneAuditAction
from ..core.geo_validation import (
    validate_point_geometry,
    validate_polygon_geometry,
    validate_multipolygon_geometry,
    validate_zone_geometry,
    compute_polygon_center,
    GeoValidationError,
)


class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., description="[longitude, latitude]")

    @field_validator("coordinates")
    @classmethod
    def check_coordinates(cls, v: List[float]) -> List[float]:
        if len(v) < 2:
            raise ValueError("Point coordinates must contain at least [longitude, latitude]")
        lon, lat = v[0], v[1]
        if lon < -180.0 or lon > 180.0:
            raise ValueError(f"Longitude {lon} out of range [-180.0, 180.0]")
        if lat < -90.0 or lat > 90.0:
            raise ValueError(f"Latitude {lat} out of range [-90.0, 90.0]")
        return [float(lon), float(lat)]


class ZoneCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Zone name")
    description: Optional[str] = Field(default="", max_length=1000)
    zone_type: ZoneType = Field(default=ZoneType.SAFE, description="safe, warning, or restricted")
    risk_level: ZoneRiskLevel = Field(default=ZoneRiskLevel.LOW, description="low, medium, high, or critical")
    status: ZoneStatus = Field(default=ZoneStatus.ACTIVE, description="active, inactive, or draft")
    boundary: Dict[str, Any] = Field(..., description="RFC 7946 GeoJSON Polygon or MultiPolygon")
    center: Optional[Dict[str, Any]] = Field(default=None, description="Optional GeoJSON Point; auto-computed if omitted")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_active: Optional[bool] = True

    @field_validator("boundary")
    @classmethod
    def validate_boundary_geojson(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return validate_zone_geometry(v, path="boundary")
        except GeoValidationError as e:
            raise ValueError(str(e))

    @field_validator("center")
    @classmethod
    def validate_center_geojson(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        try:
            return validate_point_geometry(v, path="center")
        except GeoValidationError as e:
            raise ValueError(str(e))

    @model_validator(mode="after")
    def populate_center_if_missing(self) -> "ZoneCreateRequest":
        if self.center is None and self.boundary:
            self.center = compute_polygon_center(self.boundary)
        return self


class ZoneUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    zone_type: Optional[ZoneType] = None
    risk_level: Optional[ZoneRiskLevel] = None
    status: Optional[ZoneStatus] = None
    boundary: Optional[Dict[str, Any]] = None
    center: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator("boundary")
    @classmethod
    def validate_boundary_geojson(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        try:
            return validate_zone_geometry(v, path="boundary")
        except GeoValidationError as e:
            raise ValueError(str(e))

    @field_validator("center")
    @classmethod
    def validate_center_geojson(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        try:
            return validate_point_geometry(v, path="center")
        except GeoValidationError as e:
            raise ValueError(str(e))


class ZoneStatusTransitionRequest(BaseModel):
    status: ZoneStatus
    reason: Optional[str] = Field(default=None, max_length=500)


class ZoneResponse(BaseModel):
    id: str
    zone_id: str
    name: str
    description: str
    zone_type: ZoneType
    risk_level: ZoneRiskLevel
    status: ZoneStatus
    boundary: Dict[str, Any]
    center: Dict[str, Any]
    properties: Dict[str, Any]
    is_active: bool
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "populate_by_name": True}


class ZoneTouristMapItem(BaseModel):
    zone_id: str
    name: str
    description: str
    type: str  # maps to zone_type (safe / warning / restricted)
    risk_level: str
    status: str
    geometry: Dict[str, Any]  # maps to boundary
    center: Dict[str, Any]
    properties: Dict[str, Any]

    model_config = {"populate_by_name": True}


class ZoneTouristMapResponse(BaseModel):
    zones: List[ZoneTouristMapItem]
    total: int


class ZoneListResponse(BaseModel):
    items: List[ZoneResponse]
    total: int
    skip: int
    limit: int


class ZoneAuditResponse(BaseModel):
    id: str
    audit_id: str
    zone_id: str
    action: ZoneAuditAction
    changed_by: str
    changed_at: datetime
    previous_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    change_summary: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True}
