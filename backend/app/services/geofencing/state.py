"""
TourSafe - Geofence Hysteresis State Machine & Dwell Engine

Maintains deterministic state machine per (tourist_id, zone_id):
- Prevents GPS jitter near polygon boundaries from causing rapid enter/exit oscillation
- Requires temporal / sample confirmation (hysteresis) for ambiguous boundary samples
- Computes exact timestamp-based dwell durations
- Triggers configurable dwell threshold events
- Handles staleness without generating spurious exit transitions
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from .types import (
    ActiveZoneMembership,
    ContainmentResult,
    ContainmentStatus,
    MembershipConfidence,
    ZoneMembershipState,
)

logger = logging.getLogger("toursafe.geofencing.state")

# Default hysteresis rules
ENTER_CONFIRM_SAMPLES = 2
EXIT_CONFIRM_SAMPLES = 2
DEFAULT_DWELL_THRESHOLD_SECONDS = 300.0  # 5 minutes default


class ZoneStateContext:
    """
    Internal in-memory tracking context per tourist-zone pair.
    Used for counting consecutive enter/exit candidate samples.
    """
    def __init__(self, zone_id: str):
        self.zone_id = zone_id
        self.state: ZoneMembershipState = ZoneMembershipState.OUTSIDE
        self.enter_candidate_count: int = 0
        self.exit_candidate_count: int = 0
        self.entered_at: Optional[str] = None
        self.last_seen_inside: Optional[str] = None
        self.dwell_threshold_notified: bool = False
        self.first_candidate_timestamp: Optional[str] = None


class GeofenceStateMachine:
    """
    Evaluates new location containment results against existing zone membership state
    and produces deterministic state transitions.
    """

    @staticmethod
    def parse_iso_timestamp(ts_str: Optional[str]) -> datetime:
        if not ts_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    @classmethod
    def evaluate_transition(
        cls,
        tourist_id: str,
        zone: Dict[str, Any],
        containment: ContainmentResult,
        sample_timestamp: str,
        existing_membership: Optional[ActiveZoneMembership],
        state_ctx: Optional[ZoneStateContext] = None,
    ) -> Tuple[ZoneMembershipState, Optional[str], Optional[ActiveZoneMembership]]:
        """
        Evaluates the new state for a given tourist and zone.
        Returns:
            (new_state, transition_event_type_or_None, updated_active_membership_or_None)
        
        Transition event types:
            - 'zone.entered'
            - 'zone.exited'
            - 'zone.dwell.threshold_reached'
            - 'zone.membership.uncertain'
            - 'zone.membership.stale'
        """
        zone_id = zone.get("zone_id") or zone.get("id") or "unknown_zone"
        zone_name = zone.get("name", zone_id)
        zone_type = zone.get("zone_type", "safe")
        risk_level = zone.get("risk_level", "low")
        properties = zone.get("properties", {})
        geometry_version = zone.get("updated_at")
        if isinstance(geometry_version, datetime):
            geometry_version = geometry_version.isoformat()

        dwell_threshold = float(properties.get("dwell_threshold_seconds", DEFAULT_DWELL_THRESHOLD_SECONDS))

        current_state = existing_membership.state if existing_membership else ZoneMembershipState.OUTSIDE
        if isinstance(current_state, str):
            try:
                current_state = ZoneMembershipState(current_state)
            except ValueError:
                current_state = ZoneMembershipState.OUTSIDE

        is_inside = containment.is_contained and not containment.is_boundary
        is_boundary = containment.is_boundary
        is_uncertain = containment.containment_status == ContainmentStatus.UNCERTAIN or containment.confidence_level == MembershipConfidence.UNCERTAIN

        event_to_emit: Optional[str] = None
        new_membership: Optional[ActiveZoneMembership] = None

        # ── CASE 1: Currently OUTSIDE ─────────────────────────────────────────
        if current_state == ZoneMembershipState.OUTSIDE:
            if is_inside:
                # Check for fast-path confirmation: high confidence and well inside boundary
                if containment.confidence_level == MembershipConfidence.HIGH and containment.distance_to_boundary_meters > 20.0:
                    new_state = ZoneMembershipState.INSIDE
                    entered_at = sample_timestamp
                    event_to_emit = "zone.entered"
                    new_membership = ActiveZoneMembership(
                        zone_id=zone_id,
                        name=zone_name,
                        zone_type=zone_type,
                        risk_level=risk_level,
                        state=new_state,
                        confidence_level=containment.confidence_level,
                        confidence_score=containment.confidence_score,
                        entered_at=entered_at,
                        last_seen_inside=sample_timestamp,
                        dwell_duration_seconds=0.0,
                        dwell_threshold_notified=False,
                        last_location_timestamp=sample_timestamp,
                        distance_to_boundary_meters=containment.distance_to_boundary_meters,
                        accuracy_meters=containment.accuracy_meters,
                        geometry_version=geometry_version,
                        properties=properties,
                    )
                    return new_state, event_to_emit, new_membership
                else:
                    # Near boundary or moderate accuracy -> ENTER_CANDIDATE
                    if state_ctx:
                        state_ctx.enter_candidate_count += 1
                        if state_ctx.enter_candidate_count >= ENTER_CONFIRM_SAMPLES:
                            new_state = ZoneMembershipState.INSIDE
                            entered_at = state_ctx.entered_at or sample_timestamp
                            event_to_emit = "zone.entered"
                            state_ctx.enter_candidate_count = 0
                            new_membership = ActiveZoneMembership(
                                zone_id=zone_id,
                                name=zone_name,
                                zone_type=zone_type,
                                risk_level=risk_level,
                                state=new_state,
                                confidence_level=containment.confidence_level,
                                confidence_score=containment.confidence_score,
                                entered_at=entered_at,
                                last_seen_inside=sample_timestamp,
                                dwell_duration_seconds=0.0,
                                dwell_threshold_notified=False,
                                last_location_timestamp=sample_timestamp,
                                distance_to_boundary_meters=containment.distance_to_boundary_meters,
                                accuracy_meters=containment.accuracy_meters,
                                geometry_version=geometry_version,
                                properties=properties,
                            )
                            return new_state, event_to_emit, new_membership

                    # Not yet confirmed
                    new_state = ZoneMembershipState.ENTER_CANDIDATE
                    if state_ctx and not state_ctx.entered_at:
                        state_ctx.entered_at = sample_timestamp
                    return new_state, None, None
            elif is_boundary or is_uncertain:
                # Near boundary but not clearly inside
                return ZoneMembershipState.OUTSIDE, None, None
            else:
                if state_ctx:
                    state_ctx.enter_candidate_count = 0
                return ZoneMembershipState.OUTSIDE, None, None

        # ── CASE 2: Currently ENTER_CANDIDATE ─────────────────────────────────
        elif current_state == ZoneMembershipState.ENTER_CANDIDATE:
            if is_inside:
                # Second inside sample confirms INSIDE
                new_state = ZoneMembershipState.INSIDE
                entered_at = existing_membership.entered_at if existing_membership else sample_timestamp
                event_to_emit = "zone.entered"
                if state_ctx:
                    state_ctx.enter_candidate_count = 0
                new_membership = ActiveZoneMembership(
                    zone_id=zone_id,
                    name=zone_name,
                    zone_type=zone_type,
                    risk_level=risk_level,
                    state=new_state,
                    confidence_level=containment.confidence_level,
                    confidence_score=containment.confidence_score,
                    entered_at=entered_at,
                    last_seen_inside=sample_timestamp,
                    dwell_duration_seconds=0.0,
                    dwell_threshold_notified=False,
                    last_location_timestamp=sample_timestamp,
                    distance_to_boundary_meters=containment.distance_to_boundary_meters,
                    accuracy_meters=containment.accuracy_meters,
                    geometry_version=geometry_version,
                    properties=properties,
                )
                return new_state, event_to_emit, new_membership
            else:
                # Jitter sample back outside -> reset to OUTSIDE
                if state_ctx:
                    state_ctx.enter_candidate_count = 0
                    state_ctx.entered_at = None
                return ZoneMembershipState.OUTSIDE, None, None

        # ── CASE 3: Currently INSIDE ──────────────────────────────────────────
        elif current_state == ZoneMembershipState.INSIDE:
            entered_at = existing_membership.entered_at if existing_membership else sample_timestamp
            dwell_notified = existing_membership.dwell_threshold_notified if existing_membership else False

            # Calculate actual timestamp-based dwell duration
            t_entry = cls.parse_iso_timestamp(entered_at)
            t_now = cls.parse_iso_timestamp(sample_timestamp)
            dwell_duration = max(0.0, (t_now - t_entry).total_seconds())

            if is_inside:
                # Remained inside: check dwell threshold crossing
                if not dwell_notified and dwell_duration >= dwell_threshold:
                    event_to_emit = "zone.dwell.threshold_reached"
                    dwell_notified = True

                if state_ctx:
                    state_ctx.exit_candidate_count = 0

                new_membership = ActiveZoneMembership(
                    zone_id=zone_id,
                    name=zone_name,
                    zone_type=zone_type,
                    risk_level=risk_level,
                    state=ZoneMembershipState.INSIDE,
                    confidence_level=containment.confidence_level,
                    confidence_score=containment.confidence_score,
                    entered_at=entered_at,
                    last_seen_inside=sample_timestamp,
                    dwell_duration_seconds=round(dwell_duration, 1),
                    dwell_threshold_notified=dwell_notified,
                    last_location_timestamp=sample_timestamp,
                    distance_to_boundary_meters=containment.distance_to_boundary_meters,
                    accuracy_meters=containment.accuracy_meters,
                    geometry_version=geometry_version,
                    properties=properties,
                )
                return ZoneMembershipState.INSIDE, event_to_emit, new_membership

            elif is_boundary or is_uncertain:
                # Point near boundary line -> maintain INSIDE but update confidence or mark UNCERTAIN
                if containment.confidence_level == MembershipConfidence.UNCERTAIN:
                    event_to_emit = "zone.membership.uncertain"

                new_membership = ActiveZoneMembership(
                    zone_id=zone_id,
                    name=zone_name,
                    zone_type=zone_type,
                    risk_level=risk_level,
                    state=ZoneMembershipState.UNCERTAIN if is_uncertain else ZoneMembershipState.INSIDE,
                    confidence_level=containment.confidence_level,
                    confidence_score=containment.confidence_score,
                    entered_at=entered_at,
                    last_seen_inside=sample_timestamp,
                    dwell_duration_seconds=round(dwell_duration, 1),
                    dwell_threshold_notified=dwell_notified,
                    last_location_timestamp=sample_timestamp,
                    distance_to_boundary_meters=containment.distance_to_boundary_meters,
                    accuracy_meters=containment.accuracy_meters,
                    geometry_version=geometry_version,
                    properties=properties,
                )
                return ZoneMembershipState.INSIDE, event_to_emit, new_membership

            else:
                # Sample is outside: do NOT exit immediately, enter EXIT_CANDIDATE to absorb jitter
                if state_ctx:
                    state_ctx.exit_candidate_count += 1

                # If single sample outside, transition to EXIT_CANDIDATE
                new_membership = ActiveZoneMembership(
                    zone_id=zone_id,
                    name=zone_name,
                    zone_type=zone_type,
                    risk_level=risk_level,
                    state=ZoneMembershipState.EXIT_CANDIDATE,
                    confidence_level=containment.confidence_level,
                    confidence_score=containment.confidence_score,
                    entered_at=entered_at,
                    last_seen_inside=existing_membership.last_seen_inside if existing_membership else sample_timestamp,
                    dwell_duration_seconds=round(dwell_duration, 1),
                    dwell_threshold_notified=dwell_notified,
                    last_location_timestamp=sample_timestamp,
                    distance_to_boundary_meters=containment.distance_to_boundary_meters,
                    accuracy_meters=containment.accuracy_meters,
                    geometry_version=geometry_version,
                    properties=properties,
                )
                return ZoneMembershipState.EXIT_CANDIDATE, None, new_membership

        # ── CASE 4: Currently EXIT_CANDIDATE ──────────────────────────────────
        elif current_state == ZoneMembershipState.EXIT_CANDIDATE:
            entered_at = existing_membership.entered_at if existing_membership else sample_timestamp
            t_entry = cls.parse_iso_timestamp(entered_at)
            t_now = cls.parse_iso_timestamp(sample_timestamp)
            dwell_duration = max(0.0, (t_now - t_entry).total_seconds())

            if is_inside:
                # Returned inside -> false exit alarm / jitter cancelled, return to INSIDE!
                if state_ctx:
                    state_ctx.exit_candidate_count = 0
                new_membership = ActiveZoneMembership(
                    zone_id=zone_id,
                    name=zone_name,
                    zone_type=zone_type,
                    risk_level=risk_level,
                    state=ZoneMembershipState.INSIDE,
                    confidence_level=containment.confidence_level,
                    confidence_score=containment.confidence_score,
                    entered_at=entered_at,
                    last_seen_inside=sample_timestamp,
                    dwell_duration_seconds=round(dwell_duration, 1),
                    dwell_threshold_notified=existing_membership.dwell_threshold_notified if existing_membership else False,
                    last_location_timestamp=sample_timestamp,
                    distance_to_boundary_meters=containment.distance_to_boundary_meters,
                    accuracy_meters=containment.accuracy_meters,
                    geometry_version=geometry_version,
                    properties=properties,
                )
                return ZoneMembershipState.INSIDE, None, new_membership

            else:
                # Confirmed outside (consecutive sample outside) -> confirm EXIT
                if state_ctx:
                    state_ctx.exit_candidate_count = 0
                    state_ctx.entered_at = None
                event_to_emit = "zone.exited"
                return ZoneMembershipState.OUTSIDE, event_to_emit, None

        # ── CASE 5: Currently UNCERTAIN / STALE ────────────────────────────────
        elif current_state in (ZoneMembershipState.UNCERTAIN, ZoneMembershipState.STALE):
            entered_at = existing_membership.entered_at if existing_membership else sample_timestamp
            t_entry = cls.parse_iso_timestamp(entered_at)
            t_now = cls.parse_iso_timestamp(sample_timestamp)
            dwell_duration = max(0.0, (t_now - t_entry).total_seconds())

            if is_inside:
                # GPS resumed and is inside -> restore INSIDE
                new_membership = ActiveZoneMembership(
                    zone_id=zone_id,
                    name=zone_name,
                    zone_type=zone_type,
                    risk_level=risk_level,
                    state=ZoneMembershipState.INSIDE,
                    confidence_level=containment.confidence_level,
                    confidence_score=containment.confidence_score,
                    entered_at=entered_at,
                    last_seen_inside=sample_timestamp,
                    dwell_duration_seconds=round(dwell_duration, 1),
                    dwell_threshold_notified=existing_membership.dwell_threshold_notified if existing_membership else False,
                    last_location_timestamp=sample_timestamp,
                    distance_to_boundary_meters=containment.distance_to_boundary_meters,
                    accuracy_meters=containment.accuracy_meters,
                    geometry_version=geometry_version,
                    properties=properties,
                )
                return ZoneMembershipState.INSIDE, None, new_membership
            else:
                # Confirmed outside after stale/uncertain
                event_to_emit = "zone.exited"
                return ZoneMembershipState.OUTSIDE, event_to_emit, None

        return ZoneMembershipState.OUTSIDE, None, None
