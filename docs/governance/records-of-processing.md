# TourSafe Records of Processing Activities (RoPA)

**Document Reference:** RoPA-TS-2026-V1  
**Regulatory Framework Reference:** GDPR Article 30 / India DPDP Act Section 6 & 8  
**Status:** Operational Record  

---

## 1. Activity: Real-Time Location Safety Monitoring & Geofencing

* **Purpose:** Monitor tourist position relative to authoritative geospatial safety zones and hazard areas to provide instant breach alerts and route advisories.
* **Lawful / Policy Basis:** 
  * Primary: Granular User Consent (`LOCATION_TRACKING`)
  * Emergency: Vital Interests / Protection of Life (`VITAL_INTERESTS_EMERGENCY`)
* **Data Categories Processed:** Latitude, Longitude, Altitude, Speed, Accuracy, Timestamp, Zone Association.
* **Data Subjects:** Registered tourists who have enabled safety tracking.
* **Recipients:** Automated Geofencing Engine, Authority Live Map (within authorized jurisdiction).
* **Retention:** 90 days for general trail; 730 days if linked to an active safety incident.
* **Technical & Security Controls:** TLS 1.3 in transit, AES-256 at rest, Redis live cache 120s TTL, Role-Based Access Control, NoSQL sanitization.

---

## 2. Activity: Emergency SOS & Multi-Agency Dispatch Orchestration

* **Purpose:** Process manual SOS alarms and automated sensor-triggered emergency events; dispatch nearest responder units; notify verified emergency contacts.
* **Lawful / Policy Basis:** Vital Interests of the Data Subject (Emergency Medical/Safety Response) & Legitimate Public Safety Interest.
* **Data Categories Processed:** Exact GPS Coordinates, Tourist Identity, Medical Alert Profile, Emergency Contacts, Live Sensor Quality.
* **Data Subjects:** Tourists in duress, designated emergency contacts.
* **Recipients:** Police CAD, EMS Dispatch, Assigned Responder Mobile Units, Twilio/SendGrid alert gateways.
* **Retention:** 730 days (Statutory Incident Log) or duration of Legal Hold.
* **Technical & Security Controls:** Optimistic locking, SHA-256 chained audit logs, SMS rate limiting, multi-party websocket authentication.

---

## 3. Activity: IMU Sensor Telemetry & LSTM Anomaly Inference

* **Purpose:** Ingest 50Hz accelerometer and gyroscope sensor streams to infer potential falls, vehicular crashes, or sudden immobility without continuous human surveillance.
* **Lawful / Policy Basis:** User Consent (`TELEMETRY_PROCESSING`) & Purpose Limitation.
* **Data Categories Processed:** 3-axis accelerometer and gyroscope readings, 3-second sliding window variance, LSTM reconstruction error anomaly scores.
* **Data Subjects:** Active tourists with mobile edge sensor streaming enabled.
* **Recipients:** LSTM Inference Engine, Safety Rules Fusion Subsystem.
* **Retention:** 30 days for raw telemetry; 180 days for anomaly events.
* **Technical & Security Controls:** Replay attack prevention, token binding, PII minimization (no personal identifiers in sensor matrices).

---

## 4. Activity: Digital Tourist Credential Issuance & KYC Verification

* **Purpose:** Verify foreign and domestic tourist identity documents, issue tamper-evident TSQR cryptographic credentials, and enable authorized offline/online QR verification.
* **Lawful / Policy Basis:** User Consent (`KYC_VERIFICATION`) and Tourism Authority Regulatory Compliance.
* **Data Categories Processed:** Document Type, OCR Extracted Name, DOB, Nationality, Verification Hash, QR Signature.
* **Data Subjects:** Onboarded tourists applying for credential verification.
* **Recipients:** Authorized Authority Verification Officers, Tourism Gate Personnel (QR scan only).
* **Retention:** 365 days post-trip or upon account erasure request.
* **Technical & Security Controls:** Client-side signing, HMAC-SHA256 signature verification, Zero-knowledge field sharing.

---

## 5. Activity: Authority AI Copilot Operational Decision Support

* **Purpose:** Provide grounded tactical recommendations, SOP document retrieval, and incident summarization to authorized command center dispatchers.
* **Lawful / Policy Basis:** Legitimate Operational Interest & Human Oversight Policy.
* **Data Categories Processed:** Anonymized incident summaries, SOP text, dispatcher prompt queries, tool execution traces.
* **Data Subjects:** Aggregated incident actors (PII stripped prior to LLM submission).
* **Recipients:** Authority Dispatch Officers, LLM Gateway (DPA protected).
* **Retention:** 60 days for conversation history; deleted thereafter.
* **Technical & Security Controls:** Prompt injection guardrails, PII redaction layer, cryptographic action previews, tool authorization gating.
