# TourSafe Tourist Intelligence & Authority Analytics Architecture

## 1. Executive Summary & Core Principle

The TourSafe Intelligence & Analytics Platform transforms authoritative operational data into actionable, privacy-preserving decision support for emergency command authorities, safety dispatchers, and individual tourists.

> [!IMPORTANT]
> **Decision Support Exclusivity**: Analytics components are strictly read-only and will never alter operational states, trigger automatic emergency dispatches, mutate LSTM anomaly thresholds, or modify deterministic safety rules.

---

## 2. Architectural Data Flow

```
RAW CANONICAL OPERATIONAL STREAMS
  ├── location_history & tracking_sessions
  ├── telemetry_samples & telemetry_windows
  ├── zones & zone_transitions
  ├── incidents & incident_timeline
  ├── anomaly_events
  ├── safety_decisions
  ├── responders & incident_assignments
  ├── notifications & dead_letter_queue
  └── sos_events
                  │
                  ▼
ANALYTICAL AGGREGATION & FILTERING LAYER
  ├── Time-bucketing (Hourly / Daily / Weekly / Monthly)
  ├── Noise & Jump Rejected GPS Travel Geometry
  ├── Percentile Durations (P50 / P90 / P95 / Mean)
  └── Spatial Geohash Grid with k-Anonymity Privacy Suppression
                  │
                  ▼
MULTI-TENANT REDIS CACHING & FRESHNESS
  ├── Deterministic Parameter Hashing
  ├── Dynamic TTLs based on Granularity and Age
  └── Explicit Freshness Headers (Updated At, Range, Status)
                  │
                  ▼
REST API & DECISION-SUPPORT DASHBOARDS
  ├── Authority Command Center (Overview, SLA, Zones, Heatmaps, Anomaly Ops)
  ├── Tourist Personal Trip & Safety Insights
  └── Secure Asynchronous Export Engine (CSV / JSON)
```

---

## 3. Canonical Data Source Matrix

| Analytical Domain | Canonical Operational Collections | Primary Metrics Computed |
| :--- | :--- | :--- |
| **Operations Overview** | `tourist_profiles`, `tracking_sessions`, `incidents`, `sos_events`, `safety_decisions` | Active tourists, open emergency incidents, P50 response, SOS count, safety state spread |
| **Incident Performance** | `incidents`, `incident_timeline` | P50/P90 lifecycle durations (Ack, Assign, Response, Arrival, Resolution), SLA compliance, false alarm rate |
| **Zone Intelligence** | `zones`, `zone_transitions`, `incidents`, `anomaly_events` | Unique visitors, total entries/exits, average & max dwell times, risk category incident concentration |
| **Spatial Heatmaps** | `location_history`, `incidents`, `sos_events`, `anomaly_events`, `responder_locations` | Geohash spatial density cells with $k \ge 3$ sample suppression |
| **Anomaly Intelligence** | `anomaly_events` | Episodes by model version, reconstruction score brackets, operational incident conversion rate |
| **Safety Engine Transitions** | `safety_decisions` | Time & count spread across `NORMAL`, `WATCH`, `ELEVATED`, `INCIDENT`, `UNKNOWN` states |
| **Responder Operations** | `responders`, `incident_assignments`, `responder_units` | Acceptance/rejection rates, assignment-to-arrival latency percentiles, unit utilization |
| **Notification Health** | `notifications`, `dead_letter_queue` | Sent vs Delivered distinction, delivery latency, provider success/failure breakdown |
| **Data Quality** | `location_history`, `telemetry_samples`, `zones`, `incidents` | Sensor availability, GPS accuracy distribution, timestamp completeness, geometry validity |
| **Tourist Personal Trips** | `itineraries`, `location_history`, `zone_transitions` | Real distance traveled (km), duration, visited zones, GPS accuracy rating, tracking gaps |

---

## 4. Privacy, Ethics, and Governance Safeguards

1. **No Individual Risk Profiling**: The platform strictly prohibits predictive policing, demographic scoring, or behavioral risk ranking of individual tourists.
2. **Spatial Heatmap $k$-Anonymity**: Spatial grid cells containing fewer than $k=3$ unique tourists are automatically flagged as suppressed (`weight=0.0`) to prevent de-anonymization of solitary tourist movement trails.
3. **Responder Privacy**: Operational metrics evaluate aggregate dispatch performance; no public leaderboards or punitive scoring of individual officers are exposed.
4. **Tenant & Role-Based Isolation**: Authority users only access analytics within their assigned jurisdiction and organization; tourists only access their personal trip summaries.

---

## 5. Caching & Freshness Strategy

- **Key Generation Pattern**: `toursafe:analytics:{tenant_id}:{metric}:{version}:{params_sha256}`
- **Dynamic TTL Policy**:
  - Realtime / Live Overviews: 30 seconds
  - Current Day Hourly Aggregations: 120 seconds
  - Multi-Day Historical Queries: 600 seconds
  - Immutable Past Ranges (> 48 hours old): 3,600 seconds
- **Freshness Metadata**: Every analytical response includes `data_updated_at`, `data_range_start`, `data_range_end`, `freshness_seconds`, and `data_status` (`REAL_DATA`, `PARTIAL_DATA`, `INSUFFICIENT_DATA`, `UNKNOWN`).

---

## 6. Export Engine Foundation

The asynchronous export system processes structured datasets (`CSV` or `JSON`) via background `ExportJob` documents in MongoDB `export_jobs`. Download URLs require active JWT bearer authorization matching the requester or an administrator role.
