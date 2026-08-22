# TOURSAFE — PROMPT 15
TOURIST INTELLIGENCE & AUTHORITY ANALYTICS PLATFORM
HISTORICAL SAFETY ANALYTICS
TRIP ANALYTICS
ZONE ANALYTICS
INCIDENT ANALYTICS
ANOMALY ANALYTICS
RESPONSE-TIME ANALYTICS
OPERATIONAL KPIs
SAFETY HEATMAPS
AUTHORITY DECISION SUPPORT
ANALYTICS DATA PIPELINE
REAL DATA ONLY

============================================================
PROJECT CONTINUATION
============================================================

You are continuing development of the EXISTING TourSafe repository.

Previously completed:
PROMPT 1-14 (backend foundation, profiles, zones, realtime, GPS, IMU, telemetry pipeline, LSTM training, inference state machine, geofencing, safety orchestration, emergency response, responder operations, notification infrastructure).

NOW IMPLEMENT:
THE TOURSAFE INTELLIGENCE & ANALYTICS PLATFORM.

============================================================
CORE OBJECTIVE
============================================================

Transform TourSafe's operational data into:
- historical analytics
- operational KPIs
- tourist safety insights
- zone intelligence
- incident intelligence
- anomaly intelligence
- responder performance analytics
- authority decision support
- system health analytics

The analytics layer must consume the existing canonical data.
DO NOT create parallel versions of operational records.

============================================================
CRITICAL PRINCIPLES & STRICT SCOPE
============================================================

- Analytics are DECISION SUPPORT, not automatic safety decisions.
- Do not let analytics override safety engine, incident state, or LSTM inference.
- Time bucketing (hour, day, week, month) using actual timestamps.
- Enforce date range filtering and max bounds.
- Explicit freshness indicators (data_updated_at, data_range, freshness, aggregation_level).
- P50, P90, P95 percentiles for incident and responder durations.
- Noise and jump-filtered GPS path distance calculation.
- Spatial heatmaps with k-anonymity privacy suppression.
- No demographic profiling, predictive policing, or tourist risk scoring.
- Multi-tenant Redis caching with dynamic TTLs.
- Export foundation (CSV/JSON).
- Comprehensive unit and integration tests.
- Mandatory session documentation.
