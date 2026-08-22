# TourSafe Machine Learning System Architecture

## 1. High-Level ML System Topology

TourSafe integrates kinematic machine learning into high-assurance tourist safety operations:

```
[Smartphone High-Frequency IMU (50 Hz)]
                 │
                 ▼
[Telemetry Ingestion & Quality Validation]
                 │
                 ▼ (Continuous Sample Stream)
[Deterministic 3.0s Temporal Windowing (150 Samples, 1.0s Stride)]
                 │
                 ▼
[TourSafe Preprocessor & RobustScaler (Median-IQR)]
                 │
         ┌───────┴────────────────────────┐
         ▼                                ▼
[Active Production ONNX Model]   [Candidate Model (Shadow Mode)]
         │                                │
         ▼                                ▼
[Reconstruction MSE Error]       [Candidate Score & Prediction]
         │                                │
         ▼                                ▼
[Multi-Tier Statistical Thresholds] [Shadow Parity Engine]
  - Normal (< τ_warn)                     │
  - Candidate (τ_warn ≤ e < τ_crit)       └─► [ML Ops Metrics & Parity Log]
  - Anomalous (e ≥ τ_crit)
         │
         ▼
[Temporal Persistence & Hysteresis State Machine]
         │
         ▼
[Safety Orchestration Engine (Prompt 11)] ──► [Emergency Dispatch / SOS]
```

---

## 2. Core Architectural Principles

1. **Dimensionality & Geometry**: 8 feature channels (`accel_x`, `accel_y`, `accel_z`, `gyro_x`, `gyro_y`, `gyro_z`, `accel_mag`, `gyro_mag`) evaluated over $T = 150$ timesteps ($3.0\text{ seconds}$ at $50\text{ Hz}$).
2. **Latent Bottleneck Autoencoder**: Unsupervised LSTM Autoencoder trained on normal human locomotion patterns to minimize false negatives on unseen anomalous dynamics.
3. **Dual Artifact Format**: Synchronous PyTorch state dictionary export (`model.pt`) and standardized ONNX graph export (`model.onnx`) with cryptographic SHA-256 verification and numerical parity checking ($< 10^{-4}$ tolerance).
4. **Safety Boundary Isolation**: The ML system outputs continuous anomaly scores, confidence indicators, and health states. Downstream deterministic safety orchestration remains authoritative for alerts and emergency dispatch.
5. **No Blind Replacement Principle**: Candidate models with superior benchmark validation metrics never automatically replace the active production model without explicit human approval and staging/shadow validation.
