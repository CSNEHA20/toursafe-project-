"""
TourSafe - GPS Quality & Geofence Uncertainty Evaluator

Evaluates GPS accuracy circles against polygon boundaries to prevent
false boundary crossing triggers caused by GPS jitter and uncertainty.
"""

from typing import Tuple
from .types import MembershipConfidence, ContainmentStatus, ZoneMembershipState


# Accuracy thresholds in meters
ACCURACY_EXCELLENT_METERS = 5.0
ACCURACY_GOOD_METERS = 15.0
ACCURACY_MODERATE_METERS = 30.0
ACCURACY_POOR_METERS = 50.0

# Staleness thresholds in seconds
GEOFENCE_LIVE_THRESHOLD_SEC = 15.0
GEOFENCE_RECENT_THRESHOLD_SEC = 60.0
GEOFENCE_STALE_THRESHOLD_SEC = 120.0
GEOFENCE_EXPIRED_THRESHOLD_SEC = 300.0


def categorize_gps_accuracy(accuracy_meters: float) -> str:
    """Categorize GPS accuracy into qualitative grade."""
    if accuracy_meters <= ACCURACY_EXCELLENT_METERS:
        return "EXCELLENT"
    elif accuracy_meters <= ACCURACY_GOOD_METERS:
        return "GOOD"
    elif accuracy_meters <= ACCURACY_MODERATE_METERS:
        return "MODERATE"
    elif accuracy_meters <= ACCURACY_POOR_METERS:
        return "POOR"
    else:
        return "UNRELIABLE"


def evaluate_boundary_uncertainty(
    distance_to_boundary_meters: float,
    accuracy_meters: float,
    is_contained: bool,
) -> Tuple[bool, MembershipConfidence]:
    """
    Determines if GPS uncertainty radius overlaps the zone boundary.
    Returns:
        (is_uncertain_boundary, confidence_level)
    """
    # If accuracy circle radius is greater than the distance to the boundary,
    # the true position might be on the other side of the boundary.
    if accuracy_meters > distance_to_boundary_meters:
        if distance_to_boundary_meters <= 5.0 or accuracy_meters > ACCURACY_POOR_METERS:
            return True, MembershipConfidence.UNCERTAIN
        return True, MembershipConfidence.LOW

    # Accuracy radius is strictly within the boundary margin
    if distance_to_boundary_meters >= 2.0 * accuracy_meters and accuracy_meters <= ACCURACY_GOOD_METERS:
        return False, MembershipConfidence.HIGH
    else:
        return False, MembershipConfidence.MEDIUM
