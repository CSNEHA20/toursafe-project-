# TourSafe Command Center Data Contracts & API Specification

## 1. REST Endpoints

### 1.1 `GET /api/v1/authority/command-center/snapshot`
Returns the complete operational snapshot for the authenticated authority's jurisdiction.

**Headers:**
- `Authorization: Bearer <JWT_TOKEN>`

**Response Schema (`200 OK`):**
```json
{
  "snapshot_id": "snap_9f83a2bc1d84",
  "server_time": "2026-08-22T05:00:00.000Z",
  "authority_scope": {
    "authority_id": "auth_goa_001",
    "user_id": "user_auth_1",
    "full_name": "Commander Ramesh",
    "organization_name": "Goa Police Tourism Dept",
    "designation": "Commanding Officer",
    "role": "authority",
    "jurisdiction_code": "IN-GOA-NORTH",
    "permissions": [
      "view_snapshot",
      "acknowledge_incident",
      "assess_incident",
      "assign_responder",
      "escalate_incident",
      "resolve_incident",
      "close_incident"
    ]
  },
  "kpis": {
    "active_tourists": 42,
    "open_incidents": 3,
    "sos_incidents": 1,
    "active_responders": 12,
    "unassigned_incidents": 1,
    "elevated_safety_states": 4,
    "stale_tracking_tourists": 2
  },
  "system_health": {
    "realtime": "HEALTHY",
    "telemetry": "HEALTHY",
    "ml": "HEALTHY",
    "notifications": "HEALTHY",
    "map": "HEALTHY",
    "backend": "HEALTHY",
    "details": {
      "active_ws_connections": 1,
      "ml_model_version": "lstm-v2.1-prod"
    },
    "checked_at": "2026-08-22T05:00:00.000Z"
  },
  "active_incidents": [
    {
      "incident_id": "inc_4a78bc0912d3",
      "tourist_id": "tourist_101",
      "tourist_name": "Alice Green",
      "source": "MANUAL_SOS",
      "severity": "CRITICAL",
      "status": "OPEN",
      "started_at": "2026-08-22T04:56:00.000Z",
      "created_at": "2026-08-22T04:56:00.000Z",
      "updated_at": "2026-08-22T04:56:00.000Z",
      "age_seconds": 240,
      "assigned_responder_id": null,
      "assigned_responder_name": null,
      "latitude": 15.4989,
      "longitude": 73.8278,
      "zone_id": "zone_baga_cliff",
      "zone_name": "Baga Restricted Cliff",
      "reasons": ["Manual SOS trigger by tourist"],
      "signal_summary": {},
      "timeline_summary": [
        {
          "timestamp": "2026-08-22T04:56:00.000Z",
          "action": "incident.created",
          "actor_id": "tourist_101"
        }
      ],
      "version": 1,
      "is_sos": true
    }
  ],
  "sos_queue": [],
  "tourists": [
    {
      "tourist_id": "tourist_101",
      "full_name": "Alice Green",
      "phone": "+919876543210",
      "nationality": "UK",
      "safety_state": "INCIDENT",
      "tracking_status": "active",
      "latitude": 15.4989,
      "longitude": 73.8278,
      "altitude": 14.2,
      "accuracy_m": 4.5,
      "battery_pct": 82,
      "last_updated_at": "2026-08-22T04:59:50.000Z",
      "staleness": "LIVE",
      "verification_status": "verified",
      "credential_status": "active"
    }
  ],
  "responders": [
    {
      "responder_id": "resp_01",
      "full_name": "Patrol Unit Alpha 1",
      "unit_id": "unit_alpha_1",
      "unit_name": "North Beach Patrol",
      "unit_type": "POLICE",
      "status": "AVAILABLE",
      "latitude": 15.5500,
      "longitude": 73.7600,
      "battery_pct": 95,
      "capabilities": ["FIRST_AID", "PATROL"],
      "last_location_time": "2026-08-22T04:59:45.000Z",
      "staleness": "LIVE"
    }
  ],
  "zones": [
    {
      "zone_id": "zone_001",
      "name": "Baga Restricted Cliff",
      "zone_type": "danger",
      "risk_level": "critical",
      "status": "active",
      "is_active": true,
      "center_lat": 15.5500,
      "center_lng": 73.7500,
      "active_tourists_count": 3,
      "active_incidents_count": 1
    }
  ]
}
```

---

### 1.2 `GET /api/v1/authority/command-center/system-status`
Returns real-time health for all 6 operational subsystems.

---

### 1.3 `GET /api/v1/authority/command-center/search?q={query}&type={type}`
Performs multi-entity keyword search across incidents, tourists, responders, zones, and credentials.

---

## 2. Realtime Event Payloads

### 2.1 `incident.created`
```json
{
  "event_id": "evt_inc_create_001",
  "event_type": "incident.created",
  "timestamp": "2026-08-22T05:00:00.000Z",
  "source": "backend",
  "version": 1,
  "payload": {
    "incident_id": "inc_4a78bc0912d3",
    "tourist_id": "tourist_101",
    "severity": "HIGH",
    "status": "OPEN",
    "reasons": ["IMU fall + zone dwell"],
    "location_data": { "latitude": 15.4989, "longitude": 73.8278 }
  }
}
```

### 2.2 `sos.created`
```json
{
  "event_id": "evt_sos_create_001",
  "event_type": "sos.created",
  "timestamp": "2026-08-22T05:00:00.000Z",
  "source": "backend",
  "version": 1,
  "payload": {
    "incident_id": "inc_sos_001",
    "tourist_id": "tourist_101",
    "severity": "CRITICAL",
    "status": "OPEN",
    "reasons": ["Manual SOS triggered by tourist"],
    "location_data": { "latitude": 15.4989, "longitude": 73.8278 }
  }
}
```
