# Prompt 26: Architectural & Design Decisions

## 1. Real Data Guarantee & No Simulated Values
All operational analytics endpoints aggregate exclusively from real canonical collections (`incidents`, `tracking_sessions`, `responder_profiles`, `safety_decisions`, `anomaly_events`, `risk_episodes`). When data is sparse or missing, explicit zero values or `INSUFFICIENT_DATA` statuses are returned rather than synthetic placeholders.

## 2. Multi-Tenant Jurisdiction Isolation
Non-admin authority queries are strictly constrained to their `jurisdiction_id`. System administrators can aggregate across jurisdictions without exposing individual tourist PII.

## 3. k-Anonymity Grid Suppression
Heatmaps and hotspot clusters with fewer than 3 individual tourist data points are suppressed to ensure that individuals cannot be tracked or de-anonymized through high-resolution spatial aggregations.

## 4. Bounded Uncertainty in Statistical Forecasting
Demand forecasting uses historical cyclical baselines and residual variance to generate explicit 80% prediction intervals (`[lower_bound_p10, upper_bound_p90]`). If historical records are fewer than 5, the model gracefully returns `INSUFFICIENT_DATA` rather than hallucinating predictive certainty.
