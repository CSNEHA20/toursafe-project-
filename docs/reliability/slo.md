# TourSafe Service Level Objectives (SLOs) & Error Budgets

## 1. Guiding Principles
SLOs in TourSafe are empirical targets measured continuously via the central Metrics Registry (`/api/v1/reliability/slo` and `/metrics`). We do not publish unrealistic guarantees (e.g. "100% uptime"); all targets reflect measurable architectural constraints.

---

## 2. Core Service Level Indicators (SLIs) & Objectives

| Objective Name | Target | Measurement Window | SLI Formula & Source | Error Budget Allocation |
| :--- | :--- | :--- | :--- | :--- |
| **API Availability** | **99.9%** | 30 Days Rolling | `(1 - (HTTP_5xx / Total_HTTP_Requests)) * 100`<br>*Source: Ingress Tracing Middleware* | 0.10% (approx. 43.2 minutes of downtime/month) |
| **API Latency (p95)** | **≤ 250 ms** | 5 Minutes Rolling | `p95(http_request_duration_ms)`<br>*Source: Golden Signals sliding window* | Violations > 250ms for > 15m alert on-call |
| **SOS Ingestion Reliability** | **99.99%** | 30 Days Rolling | `(1 - (SOS_Failures / SOS_Received)) * 100`<br>*Source: SubsystemMetrics SOS tracker* | 0.01% (Max 1 failure per 10,000 SOS triggers) |
| **SOS Acknowledgment Delay (p99)** | **≤ 2.0 s** | 24 Hours Rolling | `p99(sos_acknowledgment_latency_ms)`<br>*Source: Incident Operations tracker* | Breaches trigger immediate P0 page |
| **Telemetry Ingestion Success** | **99.5%** | 24 Hours Rolling | `(1 - (Dropped_Packets / Ingested_Packets)) * 100`<br>*Source: Telemetry Pipeline metrics* | 0.5% dropped packet allowance under network backpressure |
| **Real-time WebSocket Availability** | **99.9%** | 7 Days Rolling | `(1 - (Dropped_Frames / Total_Frames_Sent)) * 100`<br>*Source: ConnectionManager telemetry* | 0.1% dropped frames |

---

## 3. Error Budget Policy & Enforcement

### Budget Burn Rate Tiers
- **Burn Rate < 1x (Normal)**: Deployments and experimental feature rollouts proceed without restriction.
- **Burn Rate 2x - 5x (Elevated)**: System generates WARNING alert to SRE team; investigate slowest queries and transient downstream timeouts.
- **Burn Rate > 10x or Budget Exhausted (< 10% remaining)**:
  - **Policy Recommendation**: Freeze non-critical code deployments (e.g., UI redesigns, new analytics models).
  - Prioritize reliability fixes, index optimizations, and retry tuning.
  - Platform automatically enables `DEGRADED` or `CRITICAL_ONLY` shedding if database saturation threatens SOS pathways.

---

## 4. Alert Routing & On-Call Matrix

| Severity | Threshold / Condition | Target Audience | Notification Channel |
| :--- | :--- | :--- | :--- |
| **CRITICAL (P0)** | SOS processing failure, MongoDB unavailable, Error budget burn > 14x | Lead SRE & On-Call System Admin | PagerDuty / Emergency SMS |
| **HIGH (P1)** | Redis outage, DLQ buildup > 50 messages, API p95 > 500ms | System Administrators | Slack #alerts-critical / Email |
| **WARNING (P2)** | Slow DB query count > 20/min, ML fallback rate > 5% | Development Team | Slack #alerts-warnings |
| **INFO (P3)** | Degradation mode switched, Backup completed successfully | Operational Log | Audit Log / Metrics Dashboard |
