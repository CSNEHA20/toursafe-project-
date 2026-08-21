"""
TourSafe - Real-Time Geofencing Engine Package
"""

from .types import (
    ZoneMembershipState,
    MembershipConfidence,
    ContainmentStatus,
    ContainmentResult,
    ActiveZoneMembership,
    TouristGeofenceSnapshot,
    ZoneTransitionRecord,
    GeofenceDiagnostics,
)
from .geometry import (
    geodesic_distance_meters,
    point_to_segment_distance_meters,
    point_in_polygon,
    point_in_multipolygon,
    distance_to_geometry_boundary_meters,
    evaluate_point_containment,
    bounding_box_for_geometry,
    is_point_in_bounding_box,
)
from .quality import (
    categorize_gps_accuracy,
    evaluate_boundary_uncertainty,
)
from .state import (
    GeofenceStateMachine,
    ZoneStateContext,
)
from .repository import (
    GeofenceRepository,
    geofence_repository,
)
from .events import (
    GeofenceEventPublisher,
    geofence_event_publisher,
)
from .engine import (
    GeofenceEngine,
    geofence_engine,
)

__all__ = [
    "ZoneMembershipState",
    "MembershipConfidence",
    "ContainmentStatus",
    "ContainmentResult",
    "ActiveZoneMembership",
    "TouristGeofenceSnapshot",
    "ZoneTransitionRecord",
    "GeofenceDiagnostics",
    "geodesic_distance_meters",
    "point_to_segment_distance_meters",
    "point_in_polygon",
    "point_in_multipolygon",
    "distance_to_geometry_boundary_meters",
    "evaluate_point_containment",
    "bounding_box_for_geometry",
    "is_point_in_bounding_box",
    "categorize_gps_accuracy",
    "evaluate_boundary_uncertainty",
    "GeofenceStateMachine",
    "ZoneStateContext",
    "GeofenceRepository",
    "geofence_repository",
    "GeofenceEventPublisher",
    "geofence_event_publisher",
    "GeofenceEngine",
    "geofence_engine",
]
