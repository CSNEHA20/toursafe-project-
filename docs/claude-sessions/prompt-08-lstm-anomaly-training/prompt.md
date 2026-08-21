# TOURSAFE -- PROMPT 8
ML DATA PIPELINE + LSTM ANOMALY DETECTION TRAINING
DATASET RESEARCH
RAW IMU DATASET NORMALIZATION
WINDOW GENERATION
LSTM AUTOENCODER
ANOMALY THRESHOLDING
MODEL EVALUATION
MODEL ARTIFACT VERSIONING

============================================================
PROJECT CONTINUATION
============================================================

You are continuing development of the EXISTING TourSafe repository.

Previously completed:

PROMPT 1
- FastAPI backend
- MongoDB
- authentication
- JWT
- role-based authorization

PROMPT 2
- tourist profiles
- authority profiles
- medical information
- emergency contacts
- itinerary
- KYC foundation

PROMPT 3
- real geospatial zone database
- GeoJSON boundaries
- zone CRUD
- zone APIs
- MongoDB geospatial indexes
- zone audit foundation

PROMPT 4
- authenticated realtime communication
- realtime connection manager
- event envelope
- event registry
- frontend realtime client
- realtime event dispatcher
- Redis connection foundation

PROMPT 5
- real GPS acquisition
- foreground location tracking
- background location tracking where supported
- tracking sessions
- location validation
- Redis latest location
- MongoDB location history
- location.updated realtime event
- authority live location

PROMPT 6
- real accelerometer acquisition
- real gyroscope acquisition
- target approximately 50 Hz IMU sampling
- actual sampling-frequency measurement
- timestamps
- sequence numbers
- accelerometer/gyroscope synchronization
- derived magnitudes
- sensor quality metrics
- bounded local sensor buffer

PROMPT 7
- real telemetry ingestion
- telemetry packet contract
- authenticated telemetry
- Redis live telemetry
- durable telemetry storage
- sequence handling
- idempotency
- offline buffering foundation
- telemetry acknowledgement
- telemetry quality
- 3-second telemetry windows
- configurable window stride

NOW IMPLEMENT:

THE MACHINE-LEARNING DATA AND TRAINING PIPELINE.

============================================================
STRICT SCOPE
============================================================

This prompt implements:

1. Dataset research
2. Dataset acquisition
3. Dataset validation
4. Dataset normalization
5. Raw IMU preprocessing
6. Sampling-rate normalization where justified
7. Subject-wise data splitting
8. Data leakage prevention
9. Temporal window generation
10. Normal-motion training dataset construction
11. Abnormal-motion evaluation dataset construction
12. LSTM autoencoder
13. Training pipeline
14. Validation pipeline
15. Anomaly score calculation
16. Threshold calibration
17. Model evaluation
18. Baseline comparison
19. Model artifact creation
20. Preprocessing artifact creation
21. Experiment tracking
22. Model versioning
23. ML documentation

DO NOT implement:

- production realtime inference
- mobile on-device inference
- live anomaly detection
- geo-fencing
- geo-fence entry/exit
- automatic SOS
- emergency dispatch
- FCM
- e-FIR
- DID
- blockchain
- IPFS
- responder routing

Prompt 8 ends with:

TRAINED + EVALUATED + VERSIONED MODEL ARTIFACT.

Production inference will be implemented in Prompt 9.

============================================================
CRITICAL ML PRINCIPLE
============================================================

Do NOT build TourSafe's first anomaly detector as a simple:

activity classifier.

Do NOT make:

walking = normal
falling = anomaly

by simply training a classifier.

The first model should learn the statistical structure of:

NORMAL HUMAN MOVEMENT

and detect deviations from it.

Therefore implement:

LSTM AUTOENCODER

Primary concept:

normal sequence
      ↓
LSTM encoder
      ↓
latent representation
      ↓
LSTM decoder
      ↓
reconstructed sequence
      ↓
reconstruction error
      ↓
anomaly score

Normal sequences should generally have lower reconstruction error.

Unusual sequences may produce higher reconstruction error.

IMPORTANT:

Anomaly score does NOT mean:

danger

emergency

fall confirmed

SOS required

police required

It only means:

the movement pattern differs from what the model learned as normal.

Emergency decision logic will be implemented later.

============================================================
MANDATORY AGENTIC SESSION DOCUMENTATION
============================================================

Every Claude Code implementation session MUST be documented.

Create:

docs/
└── claude-sessions/
    └── prompt-08-lstm-anomaly-training/
        ├── prompt.md
        ├── agent-response.md
        ├── work-done.md
        ├── files-changed.md
        ├── verification.md
        ├── decisions.md
        ├── problems-and-solutions.md
        └── dataset-research.md

------------------------------------------------------------
prompt.md
------------------------------------------------------------

Copy the COMPLETE Prompt 8 into this file.
