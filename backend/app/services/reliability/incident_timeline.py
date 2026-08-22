"""
TourSafe Incident Unified Timeline & Cross-System Event Correlator.
Combines incident lifecycle, risk fusion signals, dispatches, notifications,
and external calls into an audit-compliant chronological timeline.
"""

import time
from typing import Any, Dict, List, Optional
from ...core import database as db_core


class IncidentTimelineService:
    """Reconstructs the full lifecycle timeline of an incident across all subsystems."""

    async def get_incident_timeline(self, incident_id: str) -> Dict[str, Any]:
        """Aggregate events across incident logs, dispatches, notifications, and audits."""
        db = db_core.get_database()
        timeline_events: List[Dict[str, Any]] = []

        # 1. Fetch the primary incident record
        incident = None
        try:
            incident = await db.incidents.find_one({"incident_id": incident_id})
            if not incident:
                incident = await db.incidents.find_one({"_id": incident_id})
        except Exception:
            pass

        if incident:
            timeline_events.append({
                "timestamp": incident.get("created_at", incident.get("timestamp")),
                "event_type": "INCIDENT_CREATED",
                "subsystem": "incident_lifecycle",
                "title": f"Incident Created: {incident.get('type', 'EMERGENCY')}",
                "details": {
                    "severity": incident.get("severity"),
                    "location": incident.get("location"),
                    "source": incident.get("source", "SOS_TRIGGER"),
                },
            })

            # Check status history if present
            if "status_history" in incident and isinstance(incident["status_history"], list):
                for sh in incident["status_history"]:
                    timeline_events.append({
                        "timestamp": sh.get("timestamp"),
                        "event_type": f"STATUS_{sh.get('status')}",
                        "subsystem": "incident_lifecycle",
                        "title": f"Status changed to {sh.get('status')}",
                        "details": sh,
                    })

        # 2. Fetch dispatches related to this incident
        try:
            cursor = db.emergency_dispatches.find({"incident_id": incident_id})
            dispatches = await cursor.to_list(length=20)
            for d in dispatches:
                timeline_events.append({
                    "timestamp": d.get("created_at", d.get("dispatched_at")),
                    "event_type": "RESPONDER_DISPATCHED",
                    "subsystem": "responder_dispatch",
                    "title": f"Responder {d.get('responder_id')} Dispatched",
                    "details": {
                        "dispatch_id": d.get("dispatch_id", str(d.get("_id"))),
                        "unit_type": d.get("unit_type"),
                        "eta_minutes": d.get("eta_minutes"),
                    },
                })
        except Exception:
            pass

        # 3. Fetch notifications related to this incident
        try:
            cursor = db.notifications.find({"incident_id": incident_id})
            notifications = await cursor.to_list(length=20)
            for n in notifications:
                timeline_events.append({
                    "timestamp": n.get("created_at", n.get("sent_at")),
                    "event_type": "NOTIFICATION_SENT",
                    "subsystem": "notifications",
                    "title": f"Notification to {n.get('recipient_role', 'RECIPIENT')}",
                    "details": {
                        "channel": n.get("channel"),
                        "status": n.get("status"),
                        "priority": n.get("priority"),
                    },
                })
        except Exception:
            pass

        # 4. Fetch audit logs related to this incident
        try:
            cursor = db.audit_logs.find({"resource_id": incident_id})
            audits = await cursor.to_list(length=20)
            for a in audits:
                timeline_events.append({
                    "timestamp": a.get("timestamp"),
                    "event_type": a.get("action", "AUDIT_EVENT"),
                    "subsystem": "audit",
                    "title": f"Audit: {a.get('action')}",
                    "details": {
                        "actor_id": a.get("actor_id"),
                        "changes": a.get("changes"),
                    },
                })
        except Exception:
            pass

        # Sort timeline chronologically
        timeline_events.sort(key=lambda x: str(x.get("timestamp") or ""))

        return {
            "incident_id": incident_id,
            "total_events": len(timeline_events),
            "timeline": timeline_events,
            "generated_at": time.time(),
        }


incident_timeline_service = IncidentTimelineService()
