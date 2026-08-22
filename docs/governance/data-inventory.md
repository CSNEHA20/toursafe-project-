# TourSafe Comprehensive Data Inventory

**Document Version:** 1.0.0  
**Classification:** Internal Governance & Audit  
**Effective Date:** 2026-08-22  
**Governing Principle:** Privacy by Design, Purpose Limitation, and Precision Minimization.

---

## 1. Executive Summary

This Data Inventory documents every concrete data asset, schema, and persistent entity processed within the TourSafe ecosystem across mobile edge clients, backend microservices, MongoDB collections, and Redis ephemeral caches.

---

## 2. Data Categories & Inventory Register

| Data Category | Concrete Data Elements | Source | Processing Purpose | Primary Owner | Storage Store | Baseline Retention | Authorized Access Roles | Sensitivity Classification | Safe Deletion Behavior |
|---|---|---|---|---|---|---|---|---|---|
| **IDENTITY** | `user_id`, `email`, `full_name`, `phone`, `date_of_birth`, `nationality`, `hashed_password` | Tourist Registration & Profile Forms | Authentication, Emergency Contact Verification, Credential Issuance | Identity & Access Team | MongoDB (`users`, `tourists`, `identity_profiles`) | Account Lifetime + 30-day DSR Grace | Tourist (Self), Authority Admin, Privacy Admin | `CONFIDENTIAL` / `SENSITIVE` | Soft-delete with PII anonymization (`[DELETED_USER]`) |
| **KYC** | Document Type (Passport, National ID, Aadhaar), Document Hash, Verification Status, Expiry Date | Mobile Camera / KYC Provider API | Identity validation, Digital Tourist Credential QR verification | Compliance & Identity Team | MongoDB (`kyc_documents`, `credentials`) | 365 Days after Tourist Departure | Tourist (Self), Authority KYC Reviewer | `SENSITIVE` / `CRITICAL` | Hard delete document metadata, archive verification hash |
| **CONTACT** | Emergency Contact Name, Relationship, Priority, Phone Number, Notification Preferences | Tourist Profile Configuration | Automatic SOS alerting, Multi-party incident notification | Tourist & Dispatch Team | MongoDB (`emergency_contacts`) | Active Account Lifetime | Tourist (Self), Incident Commander, Emergency Responder | `CONFIDENTIAL` | Cascade hard delete on account erasure |
| **LOCATION** | Latitude, Longitude, Altitude, Speed, Bearing, Horizontal Accuracy, Timestamp | Device GPS Receiver (Foreground/Background) | Realtime safety zone tracking, Geofence breach detection, SOS rescue | Geospatial Operations | Redis (`geo:live`, 120s TTL) & MongoDB (`locations`, `location_histories`) | 90 Days (Active Tracking) / 730 Days (Incident-Linked) | Tourist (Self), Field Responder (500m proximity/dispatch), Authority Admin | `SENSITIVE` (Operational) | Hard delete non-incident locations; preserve incident locations under legal hold |
| **TELEMETRY** | Accelerometer (x, y, z), Gyroscope (x, y, z), 3-sec Sliding Window Features, IMU Variance | Device IMU Sensors (50Hz Mobile Edge Pipeline) | Crash detection, Sudden fall inference, LSTM autoencoder anomaly scoring | ML & Safety Intelligence | Redis (`telemetry:live`) & MongoDB (`telemetry_records`) | 30 Days (Raw Telemetry) / 180 Days (Derived Features) | Safety ML Service, System Admin | `CONFIDENTIAL` (Raw Sensor Data) | Hard delete raw sensor logs past retention |
| **INCIDENT** | `incident_id`, Type (SOS, Crash, Geofence, Health), Severity, Status, Coordinates, Description | Automated Rules, Manual SOS, Authority Dispatch | Multi-agency emergency response, CAD integration, Incident lifecycle management | Incident Command Authority | MongoDB (`incidents`, `incident_timeline`) | 730 Days (2 Years) / Extended by Legal Hold | Dispatcher, Assigned Responder Units, Incident Commander, Auditor | `CRITICAL` | Block deletion if under active investigation or Legal Hold |
| **EMERGENCY** | SOS Trigger Timestamp, Countdown Cancellations, Battery Level at SOS, Signal Degradation State | Mobile SOS Button & Edge Watchdog | Immediate rescue dispatch, Duress verification, False alarm prevention | Emergency Response Orchestration | MongoDB (`emergency_events`, `sos_signals`) | 730 Days (Statutory Incident Log) | Incident Commander, Dispatcher, Police/EMS Responders | `CRITICAL` | Block deletion during open investigation |
| **RESPONDER** | Responder Unit ID, Badge, Organization, Shift Status, Live GPS Coordinates, Equipment Capabilities | Responder Mobile App & Dispatch CAD | Unit dispatch, Proximity arrival verification, Tactical coordination | Authority Operations Team | MongoDB (`responders`, `responder_units`) & Redis Live State | Active Employment Lifetime | Authority Dispatcher, System Admin, Responder (Self) | `INTERNAL` / `CONFIDENTIAL` | Deactivate profile; retain historical dispatch logs |
| **AUTHORITY** | Authority Admin Profile, Jurisdiction GeoJSON boundary, Organization Type, Role Grants | Admin Console Provisioning | Multi-tier jurisdiction governance, Policy authorization, Cross-border oversight | System Administration | MongoDB (`organizations`, `jurisdictions`, `authority_admins`) | Platform Lifetime | System Admin, Auditor | `CONFIDENTIAL` | Archive configuration; retain audit logs |
| **COMMUNICATION**| 2-Way Dispatch Chat, Audio Notes, Status Acknowledgements, Tactical System Broadcasts | Dispatch Console & Mobile Chat Stream | Responder-to-tourist comms, Scene handover coordination | Operational Communications | MongoDB (`incident_messages`, `dispatch_logs`) | 730 Days | Incident Participants, Assigned Responders, Dispatcher | `CONFIDENTIAL` | Hard delete upon incident archival (unless held) |
| **ANALYTICS** | Aggregated Heatmap Density (2-decimal geohash), Anomaly Conversion Rates, P50-P99 Response KPIs | Canonical ETL Pipeline | B2G executive intelligence, Safety zone optimization, Demand forecasting | BI & Analytics Lead | MongoDB (`analytics_aggregations`) & Redis Cache | 1095 Days (3 Years Aggregated) | Authority Executive, Analytics Viewer | `INTERNAL` (De-Identified) | Permanent rolling aggregation (no raw PII) |
| **AI** | Copilot Queries, Tool Execution Traces, RAG SOP Context Previews, Feedback Ratings | Authority AI Copilot Console | Authority decision support, Standard Operating Procedure guidance | AI Governance Team | MongoDB (`copilot_conversations`, `ai_tool_traces`) | 60 Days | Authority Officer (Self), AI Governance Officer | `INTERNAL` / `CONFIDENTIAL` | Hard delete conversations past 60 days |
| **ML** | Training Dataset Partitions, ONNX Model Weights, PSI/KS Drift Metrics, Anomaly Scores | ML Pipeline & Offline Training Harness | Realtime anomaly detection, Drift monitoring, Model registry governance | ML Engineering Team | Model Storage & MongoDB (`ml_datasets`, `model_registry`) | Indefinite (Model Artifacts) / 180 Days (Drift Logs) | ML Engineer, System Admin | `INTERNAL` | Archive versioned models; delete training partitions |
| **AUDIT** | SHA-256 Hash Chained Logs, Actor ID, Role, Action, Resource Type, Timestamp, Before/After Diff | Audit Logging Subsystem | Regulatory compliance, Non-repudiation, Security investigations | Chief Compliance Officer | MongoDB (`governance_audit_logs`) | 1825 Days (5 Years Statutory) | System Auditor (Read-Only), Security Admin | `CRITICAL` (Immutable) | Immutable append-only; hard deletion strictly prohibited |
| **SYSTEM** | Health Check Metrics, Prometheus Golden Signals, Distributed Trace Spans, Circuit Breaker States | System Monitoring Infrastructure | Reliability management, SLA/SLO enforcement, Disaster recovery | DevOps / SRE Team | In-Memory Registry & Redis | 30 Days | DevOps Engineer, System Admin | `INTERNAL` | Automatic rolling TTL expiry |

---

## 3. Data Classification Tier Definitions

1. **PUBLIC**: Open safety zone definitions, verified tourist credential QR schemas, public portal contact endpoints.
2. **INTERNAL**: Aggregated analytics, system health metrics, non-sensitive organization definitions.
3. **CONFIDENTIAL**: Tourist profiles, emergency contacts, operational messages, AI copilot traces.
4. **SENSITIVE**: Exact GPS coordinates, live IMU telemetry streams, KYC document metadata.
5. **CRITICAL**: Emergency SOS events, live incident dispatch streams, cryptographic secrets, immutable SHA-256 audit logs.
