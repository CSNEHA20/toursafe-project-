"""
TourSafe Manual SOS Ingestion & Processing Service

Coordinates:
- Manual SOS initiation from authenticated tourist mobile app
- Server-side authoritative GPS location resolution (with stale/no-gps detection)
- Strict client-request-id idempotency and active-incident deduplication
- Automatic creation or association with incident command workflow (IncidentSource.MANUAL_SOS)
- Realtime event broadcasting and emergency contact notification
- Honest state tracking with no fake automated external dispatch claims
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...schemas.emergency import (
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    LocationSnapshot,
    SOSCancelRequest,
    SOSRequest,
    SOSResponse,
)
from ...schemas.safety import IncidentRecord
from ..location_service import calculate_staleness, location_service
from ..safety.events import safety_event_publisher
from .incident_service import incident_service

logger = logging.getLogger("toursafe.emergency.sos")


class SOSService:
    """
    Emergency SOS Ingestion & Management Service.
    """

    async def trigger_sos(
        self,
        tourist_id: str,
        req: SOSRequest,
    ) -> SOSResponse:
        """
        Processes an emergency SOS request from an authenticated tourist.
        """
        db = get_database()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # 1. Idempotency Check by client_request_id
        existing_sos_by_client_id = await db.sos_events.find_one({"client_request_id": req.client_request_id})
        if existing_sos_by_client_id:
            logger.info(
                "Idempotent SOS hit for client_request_id %s (tourist %s)",
                req.client_request_id,
                tourist_id,
            )
            return SOSResponse(
                sos_id=existing_sos_by_client_id["sos_id"],
                incident_id=existing_sos_by_client_id.get("incident_id", "none"),
                status=existing_sos_by_client_id.get("status", "RECEIVED"),
                created_at=existing_sos_by_client_id.get("created_at", now_iso),
                tourist_id=tourist_id,
                location_status=existing_sos_by_client_id.get("location_status", "UNKNOWN"),
                location=LocationSnapshot(**existing_sos_by_client_id["location"]) if existing_sos_by_client_id.get("location") else None,
                acknowledged=existing_sos_by_client_id.get("acknowledged", False),
                message="SOS request already received and active in command center.",
            )

        # 2. Check for active open incident deduplication
        existing_active_inc = await incident_service.get_active_incident_for_tourist(tourist_id)
        if existing_active_inc:
            logger.info(
                "Active incident %s already exists for tourist %s. Linking SOS.",
                existing_active_inc.incident_id,
                tourist_id,
            )

        # 3. Resolve Authoritative Server GPS Location
        location_snapshot = None
        loc_status = "NO_GPS"

        try:
            live_res = await location_service.get_live_location(tourist_id)
            if live_res and live_res.location:
                st_val = live_res.staleness.value if hasattr(live_res.staleness, "value") else str(live_res.staleness)
                loc_status = "CURRENT" if st_val in ("LIVE", "RECENT") else "STALE"
                location_snapshot = LocationSnapshot(
                    latitude=live_res.location.latitude,
                    longitude=live_res.location.longitude,
                    altitude=live_res.location.altitude,
                    accuracy=live_res.location.accuracy,
                    speed=live_res.location.speed,
                    timestamp=live_res.timestamp or now_iso,
                    location_status=loc_status,
                )
        except Exception as loc_err:
            logger.warning("Error fetching live GPS for tourist %s: %s", tourist_id, loc_err)

        if not location_snapshot and req.latitude is not None and req.longitude is not None:
            # Fallback to client-provided GPS hint with STALE/CLIENT_HINT flag
            loc_status = "CLIENT_HINT"
            location_snapshot = LocationSnapshot(
                latitude=req.latitude,
                longitude=req.longitude,
                accuracy=req.accuracy,
                timestamp=req.timestamp or now_iso,
                location_status="CLIENT_HINT",
            )

        # 4. Create or Associate Incident Record
        if existing_active_inc:
            incident = existing_active_inc
            # Update incident severity to CRITICAL for manual SOS
            if incident.severity != IncidentSeverity.CRITICAL:
                incident.severity = IncidentSeverity.CRITICAL
                await db.incidents.update_one(
                    {"incident_id": incident.incident_id},
                    {"$set": {"severity": IncidentSeverity.CRITICAL.value, "updated_at": now_iso}},
                )
            if location_snapshot:
                await incident_service.update_location(incident.incident_id, location_snapshot.model_dump())
            await incident_service.add_incident_note(
                incident_id=incident.incident_id,
                author_id=tourist_id,
                author_role="tourist",
                content=f"[Manual SOS Retriggered]: {req.reason or 'Tourist pressed SOS button'}",
            )
        else:
            incident = await incident_service.create_incident(
                tourist_id=tourist_id,
                source=IncidentSource.MANUAL_SOS,
                severity=IncidentSeverity.CRITICAL,
                session_id=req.session_id,
                reasons=[f"Manual SOS Triggered by Tourist: {req.reason or 'Emergency'}"],
                location_data=location_snapshot.model_dump() if location_snapshot else None,
                actor_id=tourist_id,
                actor_type="TOURIST",
            )

        # 5. Persist SOS Event Record
        sos_id = f"sos_{uuid.uuid4().hex[:12]}"
        sos_doc = {
            "sos_id": sos_id,
            "client_request_id": req.client_request_id,
            "tourist_id": tourist_id,
            "session_id": req.session_id,
            "incident_id": incident.incident_id,
            "status": "RECEIVED",
            "category": req.category,
            "reason": req.reason,
            "location_status": loc_status,
            "location": location_snapshot.model_dump() if location_snapshot else None,
            "acknowledged": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await db.sos_events.insert_one(sos_doc)

        # 6. Broadcast sos.created event
        await safety_event_publisher.publish_sos_created(sos_doc, tourist_id=tourist_id)

        return SOSResponse(
            sos_id=sos_id,
            incident_id=incident.incident_id,
            status="RECEIVED",
            created_at=now_iso,
            tourist_id=tourist_id,
            location_status=loc_status,
            location=location_snapshot,
            acknowledged=False,
            message="Emergency SOS transmitted to TourSafe Command Center. Assistance is being coordinated.",
        )

    async def cancel_sos(
        self,
        tourist_id: str,
        sos_id: str,
        req: SOSCancelRequest,
    ) -> Dict[str, Any]:
        """
        Allows tourist to cancel their own manual SOS with mandatory explanation.
        """
        db = get_database()
        sos_doc = await db.sos_events.find_one({"sos_id": sos_id, "tourist_id": tourist_id})
        if not sos_doc:
            raise ValueError(f"SOS '{sos_id}' not found for authenticated tourist")

        incident_id = sos_doc.get("incident_id")
        if incident_id:
            incident = await incident_service.get_incident(incident_id)
            if incident and incident.source == IncidentSource.MANUAL_SOS:
                await incident_service.cancel_incident(
                    incident_id=incident_id,
                    actor_id=tourist_id,
                    actor_type="TOURIST",
                    cancellation_reason=f"Tourist cancelled SOS: {req.reason}",
                    is_false_alarm=False,
                    notes=req.reason,
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.sos_events.update_one(
            {"sos_id": sos_id},
            {"$set": {"status": "CANCELLED", "cancellation_reason": req.reason, "updated_at": now_iso}},
        )

        return {
            "sos_id": sos_id,
            "status": "CANCELLED",
            "message": "SOS has been successfully cancelled.",
        }

    async def get_active_sos_for_tourist(self, tourist_id: str) -> Optional[Dict[str, Any]]:
        db = get_database()
        doc = await db.sos_events.find_one(
            {"tourist_id": tourist_id, "status": "RECEIVED"},
            sort=[("created_at", -1)],
        )
        if not doc:
            return None
        # Remove Mongo _id
        doc.pop("_id", None)
        return doc


sos_service = SOSService()
