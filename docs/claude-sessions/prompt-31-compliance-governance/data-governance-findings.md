# Data Governance Findings — Prompt 31

## 1. Concrete Inventory Results
- **Active Collections Inspected:** `users`, `tourists`, `identity_profiles`, `kyc_documents`, `credentials`, `locations`, `location_histories`, `telemetry_records`, `telemetry_windows`, `anomaly_events`, `incidents`, `incident_timeline`, `emergency_events`, `responders`, `responder_units`, `organizations`, `jurisdictions`, `incident_messages`, `dispatch_logs`, `copilot_conversations`, `ml_datasets`, `model_registry`, `governance_audit_logs`.
- **Classification Consistency:** Mapped directly to Prompt 29 zero-trust tiers (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `SENSITIVE`, `CRITICAL`) with zero contradictions.

## 2. Lineage & Processing Chains
- **Telemetry Lineage:** $50\text{Hz IMU} \longrightarrow \text{3-sec Window Features} \longrightarrow \text{LSTM Autoencoder Anomaly Score} \longrightarrow \text{Safety Rule Aggregator} \longrightarrow \text{Emergency Incident} \longrightarrow \text{Responder Dispatch}$.
- **AI Tool Lineage:** $\text{Dispatcher Prompt} \longrightarrow \text{PII Redactor} \longrightarrow \text{SOP Vector Retrieval} \longrightarrow \text{LLM Recommendation} \longrightarrow \text{5-min Preview Token} \longrightarrow \text{Human Action Confirmation} \longrightarrow \text{Audit Log}$.
