# TourSafe Operational Workflows & Playbooks

This document specifies the end-to-end operational workflows implemented across the TourSafe B2G Government Safety platform.

---

## 1. Tourist Identity & Verification Workflow (KYC → TSQR Credential)

```mermaid
sequenceDiagram
    autonumber
    actor T as Tourist
    participant M as Mobile App
    participant B as Backend API
    participant O as OCR & Identity Engine
    participant DB as Postgres / PostGIS
    actor A as District Authority

    T->>M: Enter Travel Details & Upload Govt ID (Aadhaar/Passport)
    M->>B: POST /api/v1/tourists/kyc/submit
    B->>O: Verify Document Integrity & Extract Metadata
    O-->>B: Extraction Result (Score > 0.92)
    B->>DB: Store Tourist Profile (KYC_PENDING)
    A->>B: GET /api/v1/admin/kyc/queue
    A->>B: POST /api/v1/admin/kyc/{id}/approve
    B->>DB: Issue Ed25519 Signed TSQR Credential
    B-->>M: Push Notification: "KYC Verified • Digital Pass Active"
    M->>T: Display Interactive Verifiable TSQR Code
```

---

## 2. High-Frequency Anomaly Detection & Signal Fusion Workflow

```mermaid
sequenceDiagram
    autonumber
    actor T as Tourist
    participant S as IMU Sensors (50Hz)
    participant E as Mobile Edge Engine
    participant B as Backend Telemetry Ingestion
    participant AI as LSTM Inference Engine
    participant G as Geofence Processor
    participant F as Signal Aggregator
    participant C as Command Center

    S->>E: Stream Accel & Gyro Samples (50Hz)
    E->>E: Evaluate Kinematics Magnitude & Jitter
    E->>B: POST /api/v1/telemetry/batch (Compressed Frames)
    par Parallel Evaluation
        B->>AI: Stream Frames into Bidirectional LSTM
        AI->>AI: Infer Fall / Collision Anomaly Score (e.g. 0.94)
    and
        B->>G: PostGIS Spatial Intersects (Hazard Zone / Buffer)
        G->>G: Detect Perimeter Breach: "Hazard Zone: Pillar Rocks Cliff"
    end
    AI->>F: Emit Anomaly Signal (HIGH)
    G->>F: Emit Geofence Breach Signal (CRITICAL)
    F->>F: Compute Fused Safety Risk Score (0.92 -> ELEVATED_RISK)
    F->>C: Realtime WebSocket Broadcast: `incident.candidate_created`
```

---

## 3. Emergency SOS & Multi-Agency Dispatch Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor T as Tourist
    participant M as Tourist Mobile App
    participant B as Backend Incident Engine
    participant C as Authority Command Center
    participant R as Field Responder Unit
    participant SMS as SMS / Voice Gateway

    T->>M: Press & Hold SOS Button (3s Countdown)
    M->>B: POST /api/v1/sos/trigger (Lat, Lng, Accuracy, Battery)
    par Dispatch Notification
        B->>SMS: Send Emergency Broadcast to Designated Relatives
    and
        B->>C: Realtime WebSocket: `incident.created` (CRITICAL)
    end
    C->>C: Auto-Identify Nearest Responder via Haversine / ETA Matrix
    C->>B: POST /api/v1/incidents/{id}/assign (responder_id: R-102)
    B->>R: Push Notification: "Immediate Mission Assignment • Ref: INC-902"
    R->>B: POST /api/v1/responders/me/status (EN_ROUTE)
    B-->>M: Update Tourist App: "Responder Officer Rajesh Assigned • ETA 4 mins"
    R->>B: POST /api/v1/responders/me/status (ON_SCENE)
    R->>B: POST /api/v1/incidents/{id}/resolve (Field Assessment Notes)
    B->>C: Update Command Center: Incident Resolved
```

---

## 4. Sovereign Privacy Management (DPDP Act 2023 / GDPR DSR)

```mermaid
sequenceDiagram
    autonumber
    actor T as Tourist
    participant M as Privacy Center Modal
    participant B as Privacy API
    participant H as Legal Hold & Retention Worker
    participant DB as Encrypted Database
    actor A as Compliance Officer

    T->>M: Toggle Telemetry Processing Consent -> OFF
    M->>B: POST /api/v1/privacy/consents/withdraw
    B->>DB: Record Consent Withdrawal with Cryptographic Audit Trail
    T->>M: Submit Right-to-Erasure DSR Request
    M->>B: POST /api/v1/privacy/requests (Type: DELETION)
    B->>DB: Queue DSR (Status: SUBMITTED, 72h Deadline)
    A->>B: Check Active Legal Holds (Target Scope ID)
    alt Legal Hold Active
        B-->>A: Deletion Blocked by Legal Hold #LH-042 (Warrant/Investigation)
    else No Hold
        A->>B: POST /api/v1/privacy/requests/{id}/review (APPROVE)
        B->>H: Execute Cryptographic Data Shredding on Non-Essential Tables
        B-->>M: DSR Completed • Verification Audit Certificate Emitted
    end
```
