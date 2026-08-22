# TourSafe ML Training & Operational Lifecycle Guide

This guide describes the complete end-to-end procedure for engineering datasets, training LSTM models, validating artifacts, and managing production deployments.

---

## 1. Step-by-Step Training Pipeline

```
1. Collect Canonical Telemetry (MongoDB telemetry_samples & telemetry_windows)
       │
2. Validate Raw Sensor Streams (data_validator checks ranges, timestamps, sequence continuity)
       │
3. Build & Partition Dataset (dataset_builder with anti-leakage guards & SHA-256 hash)
       │
4. Feature Extraction & Robust Normalization (features_v1, fit scaler strictly on train set)
       │
5. Train PyTorch LSTM Autoencoder (parameterized hyperparameters, seed tracking, early stopping)
       │
6. Calibrate Multi-Tier Decision Thresholds (calibrated on validation normal reconstruction scores)
       │
7. Benchmark Evaluation (ROC-AUC, PR-AUC, F1, precision, recall, FPR, FNR, latency)
       │
8. Export Dual Model Artifacts (model.pt + model.onnx with numerical parity check & checksums)
       │
9. Register Candidate Model in ModelRegistry (Initial status: TRAINED)
       │
10. Automated Validation Gate (checks artifact completeness, checksums, scaler, ONNX smoke test)
       │
11. Explicit Human Approval (Authorized operator review & sign-off)
       │
12. Staging / Shadow Deployment (Parallel live testing on streaming telemetry without safety impacts)
       │
13. Production Promotion (Authoritative production pointer update)
       │
14. Continuous Monitoring & Drift Detection (PSI & KS-test tracking against training baseline)
       │
15. Instant Rollback (Safe fallback to prior approved model if regression occurs)
```

---

## 2. API Quick Reference

### Queue Training Job
```http
POST /api/v1/ml/training/jobs
Content-Type: application/json
Authorization: Bearer <ADMIN_JWT>

{
  "model_version": "lstm-anomaly-v2",
  "dataset_version": "dataset_v2",
  "feature_version": "features_v1",
  "hyperparameters": {
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 40,
    "hidden_dims": [64, 32],
    "latent_dim": 32,
    "dropout": 0.1
  }
}
```

### Validate Candidate Model
```http
POST /api/v1/ml/models/lstm-anomaly-v2/validate
Authorization: Bearer <ADMIN_JWT>
```

### Approve Candidate Model
```http
POST /api/v1/ml/models/lstm-anomaly-v2/approve
Content-Type: application/json
Authorization: Bearer <ADMIN_JWT>

{
  "reason": "Test benchmark demonstrated 0.94 F1 and 0.96 ROC-AUC with zero leakage."
}
```

### Deploy to Production
```http
POST /api/v1/ml/models/lstm-anomaly-v2/deploy
Content-Type: application/json
Authorization: Bearer <ADMIN_JWT>

{
  "reason": "Passed 48-hour shadow mode with 99.8% agreement rate and 0.45ms latency.",
  "target_status": "PRODUCTION"
}
```

### Rollback Model
```http
POST /api/v1/ml/models/lstm-anomaly-v1/rollback
Content-Type: application/json
Authorization: Bearer <ADMIN_JWT>

{
  "reason": "Observed localized false alarm spike in specific terrain."
}
```
