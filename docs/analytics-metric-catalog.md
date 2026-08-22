# TourSafe Operational Analytics Metric Catalog & Data Lineage

## 1. Overview
This document defines every canonical KPI, operational metric, statistical aggregation, and privacy tier across the TourSafe analytics platform. All metrics are calculated deterministically from real operational telemetry, incident lifecycles, and responder transitions.

---

## 2. Executive Operational KPIs

| Metric Key | Display Name | Source Collection | Aggregation Formula / Method | Update Cadence | Privacy Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `active_tourists` | Active Tourists | `tracking_sessions`, `tourist_profiles` | `count(distinct tourist_id WHERE status == 'ACTIVE')` | Real-time (15s) | Tier 3 (Aggregated) |
| `active_trips` | Active Tourist Itineraries | `tourist_itineraries` | `count(distinct id WHERE status == 'ACTIVE')` | Real-time (15s) | Tier 3 (Aggregated) |
| `active_incidents` | Active Open Incidents | `incidents` | `count(incident_id WHERE status IN ['OPEN', 'INVESTIGATING', 'RESPONDING', 'DISPATCHED'])` | Real-time (15s) | Tier 2 (Authority) |
| `open_sos_count` | Open SOS Emergencies | `incidents`, `sos_events` | `count(incident_id WHERE incident_source == 'MANUAL_SOS' AND status != 'RESOLVED')` | Real-time (15s) | Tier 2 (Authority) |
| `responders_available` | Available Responders | `responder_profiles` | `count(responder_id WHERE status == 'ACTIVE' AND is_available == True)` | Real-time (15s) | Tier 2 (Authority) |
| `responders_assigned` | Responders Dispatched | `responder_profiles` | `count(responder_id WHERE status == 'ACTIVE' AND is_available == False)` | Real-time (15s) | Tier 2 (Authority) |
| `median_response_time` | Median Response Time (P50) | `incidents.timeline` | `P50(t_responding - t_started)` | 5 minutes | Tier 2 (Authority) |
| `p90_response_time` | 90th Percentile Response Time | `incidents.timeline` | `P90(t_responding - t_started)` | 5 minutes | Tier 2 (Authority) |
| `p95_response_time` | 95th Percentile Response Time | `incidents.timeline` | `P95(t_responding - t_started)` | 5 minutes | Tier 2 (Authority) |
| `escalation_rate` | Incident Escalation Rate | `incidents` | `count(escalation_level > 0) / count(total_incidents)` | 5 minutes | Tier 2 (Authority) |

---

## 3. Incident Lifecycle & Aging Metrics

| Metric Key | Display Name | Definition & Aggregation | SLA / Threshold |
| :--- | :--- | :--- | :--- |
| `time_to_acknowledge` | Time to Acknowledge (TTA) | Duration between incident creation and authority acknowledgment | P90 <= 300 seconds |
| `time_to_dispatch` | Time to Dispatch (TTD) | Duration between creation and first responder assignment | P90 <= 480 seconds |
| `time_to_arrival` | Time to On-Scene Arrival | Duration between assignment and responder arrival at coordinates | P90 <= 900 seconds |
| `time_to_resolution` | Time to Resolution (TTR) | Duration between creation and final incident resolution | P90 <= 3600 seconds |
| `incident_backlog_aging` | Incident Aging Distribution | Discrete buckets: `<5m`, `5-15m`, `15-30m`, `30+m` | Zero incidents in `30+m` bucket |

---

## 4. Safety State & Reliability Indicators

| Metric Key | Display Name | Definition | System Significance |
| :--- | :--- | :--- | :--- |
| `unknown_safety_state_rate` | UNKNOWN Safety State Rate | `count(state == 'UNKNOWN') / count(total_safety_decisions)` | Primary metric for GPS loss, telemetry gaps, and sensor health |
| `unknown_state_duration` | UNKNOWN State Total Duration | Sum of seconds tourists spent in `UNKNOWN` state | Quantifies network coverage blindspots |
| `risk_episodes_active` | Active Risk Episodes | `count(risk_episodes WHERE status == 'ACTIVE')` | Real-time aggregate of anomaly persistence |
| `risk_recovery_rate` | Risk Episode Recovery Rate | `count(cleared_without_incident) / count(total_episodes)` | Evaluates proactive zone warning effectiveness |

---

## 5. Privacy & Data Protection Rules

1. **k-Anonymity Grid Suppression**:
   - Any spatial grid cell or hotspot with `< 3` tourist data points is automatically suppressed to prevent individual location de-anonymization.
2. **PII Masking**:
   - All tourist IDs in analytics exports and audit logs are cryptographically pseudononymized using SHA-256 tokens (`ANON_xxxxxxxx`).
3. **Multi-Tenant Isolation**:
   - Authority queries are bounded strictly to their `jurisdiction_id`. System administrator queries aggregate without exposing cross-jurisdictional PII.
