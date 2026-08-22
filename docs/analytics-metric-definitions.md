# TourSafe Analytics Metric Definitions

This document defines the mathematical formulas, canonical data sources, filter criteria, freshness characteristics, and known limitations for all operational and analytical metrics implemented in TourSafe Prompt 15.

---

## 1. Operations Overview Metrics

### Active Tourists
- **Definition**: Number of registered tourist accounts with active tracking enabled and current session status.
- **Source**: `tourist_profiles` collection (`{"is_active": true}`).
- **Formula**: $\sum \mathbb{I}(\text{profile.is\_active} = \text{true})$
- **Freshness**: Live query (uncached / 30s TTL).
- **Limitations**: Reflects account state; does not guarantee active GPS satellite lock if device is in a tunnel.

### Open Incidents
- **Definition**: Number of ongoing safety emergencies currently in non-terminal states.
- **Source**: `incidents` collection (`{"status": {"$in": ["OPEN", "ACKNOWLEDGED", "ASSESSING", "ASSIGNED", "RESPONDING", "ESCALATED"]}}`).
- **Formula**: $\sum \mathbb{I}(\text{incident.status} \in \text{ACTIVE\_STATES})$
- **Freshness**: Realtime operational query.

### SOS Events Today
- **Definition**: Total count of manual emergency SOS requests triggered by tourists within the evaluated window.
- **Source**: `sos_events` collection (`{"timestamp": {"$gte": start_iso, "$lte": end_iso}}`).
- **Formula**: $\text{Count}(\text{sos\_events})$

---

## 2. Incident Lifecycle & SLA Performance

### Time to Acknowledge ($T_{\text{ack}}$)
- **Definition**: Duration in seconds from initial incident creation until formal acknowledgement by an authority operator.
- **Source**: `incidents.started_at` to `incidents.acknowledged_at`.
- **Formula**: $T_{\text{ack}} = \text{Epoch}(t_{\text{ack}}) - \text{Epoch}(t_{\text{start}})$
- **Aggregations**: Computed as P50, P90, P95, Mean, Min, and Max. Missing timestamps are reported as `N/A`.

### Time to Assignment ($T_{\text{assign}}$)
- **Definition**: Elapsed time in seconds between incident creation and the assignment of a field responder or unit.
- **Source**: `incidents.started_at` to `timeline` event with `action == "incident.assigned"`.
- **Formula**: $T_{\text{assign}} = \text{Epoch}(t_{\text{assigned\_event}}) - \text{Epoch}(t_{\text{start}})$

### Time to Response ($T_{\text{resp}}$)
- **Definition**: Time taken from incident creation to responder acceptance and response commencement.
- **Source**: `incidents.started_at` to `timeline` event `incident.responding` or `assignment.accepted`.

### Time to Arrival ($T_{\text{arr}}$)
- **Definition**: Time taken from incident creation until responder reaches verified physical arrival radius ($\le 500\text{m}$) on scene.
- **Source**: `incidents.started_at` to `timeline` event `assignment.arrived`.

### Time to Resolution ($T_{\text{res}}$)
- **Definition**: Total duration from incident creation until full stabilization and resolution.
- **Source**: `incidents.started_at` to `incidents.resolved_at`.

### SLA Compliance Rate
- **Definition**: Percentage of resolved incidents whose total duration was within the configured operational SLA threshold (Default: 900 seconds / 15 minutes).
- **Formula**:
  $$\text{SLA Compliance Rate} = \left( \frac{N_{\text{within\_sla}}}{N_{\text{evaluated}}} \right) \times 100\%$$

### False Alarm Rate
- **Definition**: Percentage of incidents closed with resolution category classified as `FALSE_ALARM`.
- **Formula**:
  $$\text{False Alarm Rate} = \frac{\sum \mathbb{I}(\text{resolution\_category} = \text{'FALSE\_ALARM'})}{N_{\text{total\_incidents}}}$$
- **Limitations**: Only computed for closed/resolved incidents with verified on-scene classification.

---

## 3. Zone Intelligence Metrics

### Zone Entries & Exits
- **Definition**: Discrete spatial boundary transition events confirmed by the point-in-polygon geofencing engine.
- **Source**: `zone_transitions` collection (`event_type == "ENTRY"` or `event_type == "EXIT"`).
- **Formula**: $\sum \mathbb{I}(\text{event\_type} = \text{TYPE} \land \text{zone\_id} = Z)$

### Average Dwell Time
- **Definition**: Average duration in seconds tourists continuously remain within a zone boundary.
- **Source**: `zone_transitions` collection (`event_type == "DWELL"`).
- **Formula**: $\bar{T}_{\text{dwell}} = \frac{1}{M} \sum_{i=1}^M \text{dwell\_duration\_seconds}_i$

---

## 4. GPS Distance & Path Metrics

### Cumulative Travel Distance (km)
- **Definition**: True great-circle distance traversed by a tourist based on ordered GPS samples, filtered for noise and jumps.
- **Source**: `location_history` collection sorted chronologically.
- **Filter Rules**:
  - Exclude samples with $\text{accuracy} > 100.0\text{m}$.
  - Exclude stationary jitter with $\Delta d < 2.0\text{m}$.
  - Exclude non-plausible jumps with speed $v = \Delta d / \Delta t > 70.0\text{ m/s}$ ($\sim 252\text{ km/h}$).
- **Formula**:
  $$\text{Distance (km)} = \frac{1}{1000} \sum_{k=1}^{P-1} \text{Haversine}(p_k, p_{k+1})$$

---

## 5. Anomaly Intelligence & Model Conversion

### Operational Conversion Rate
- **Definition**: Proportion of observed LSTM autoencoder reconstruction anomaly episodes that resulted in an active safety incident.
- **Source**: `anomaly_events` collection.
- **Formula**:
  $$\text{Conversion Rate} = \frac{N_{\text{episodes\_with\_associated\_incident}}}{N_{\text{total\_episodes}}}$$
- **Wording Standard**: Explicitly designated as *Operational Conversion Rate* rather than "AI Model Accuracy" because ground truth without authority triage is undefined.

---

## 6. Notification Telemetry Metrics

### Delivery Success Rate
- **Definition**: Ratio of confirmed delivered notifications to total dispatched notifications.
- **Source**: `notifications` collection.
- **Formula**:
  $$\text{Success Rate} = \left( \frac{N_{\text{DELIVERED}}}{N_{\text{SENT}} + N_{\text{DELIVERED}}} \right) \times 100\%$$
- **Distinction**: `SENT` represents provider handover; `DELIVERED` represents terminal receipt confirmation.
