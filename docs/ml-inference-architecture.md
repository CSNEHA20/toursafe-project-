# TourSafe Real-Time ML Inference Architecture

## 1. System Overview & Safety Principles

The TourSafe Real-Time ML Inference Service bridges the high-frequency physical telemetry pipeline (~50 Hz multi-axial IMU kinematics) with a deep learning LSTM Autoencoder to detect anomalous motion signatures (e.g. violent shaking, erratic drops, high-G impacts).

```
+-------------------------------------------------------------------------------+
|                           TOURSAFE SAFETY PRINCIPLE                           |
|                                                                               |
|   A high reconstruction error indicates an ANOMALOUS SENSOR PATTERN.          |
|   It does NOT independently determine an EMERGENCY or trigger an SOS.         |
|                                                                               |
|   LSTM Anomaly -> Anomaly Event -> Contextual Safety Engine -> Incident / SOS |
+-------------------------------------------------------------------------------+
```

---

## 2. End-to-End Pipeline Architecture

```
[Physical IMU Sensors (50 Hz)]
             │ (ax, ay, az, gx, gy, gz)
             ▼
[Telemetry Ingestion Pipeline]
             │ 3-second Temporal Sliding Windows (1.0s Stride)
             ▼
[TelemetryWindowEngine]
             │ Validated TelemetryWindow (T=150, D=8)
             ▼
[Bounded Inference Queue] (Capacity: 1000, Non-blocking backpressure)
             │ FIFO Dequeue
             ▼
[Inference Preprocessor]
             │ 1. IMU Feature Extraction (6 raw + 2 L2 vector magnitudes)
             │ 2. Exact 50 Hz Grid Resampling (IMUResampler)
             │ 3. Robust IQR Scaler Transform (TourSafeRobustScaler)
             ▼
[Model Loader & Inference Engine]
             │ ONNX Runtime / PyTorch (T=150, D=8) -> Reconstructed Tensor
             ▼
[Anomaly Scorer]
             │ Reconstruction MSE = (1 / (T*D)) * sum((X - X_hat)^2)
             ▼
[Temporal Persistence & Hysteresis State Machine]
             │ States: NORMAL <-> CANDIDATE <-> ANOMALOUS <-> RECOVERING
             │ Anomaly Threshold: 5.804714 | Recovery Threshold: 4.934007
             ▼
[Anomaly Episode Manager & Deduplication]
             │ Sustained anomaly -> Single active episode updated
             │ Start -> anomaly.detected | Cleared -> anomaly.cleared
             ▼
[Storage & Realtime Synchronization]
      ├──> [Redis Live State]: toursafe:anomaly:active:{tourist_id} (TTL: 180s)
      ├──> [MongoDB Persistence]: anomaly_events collection
      └──> [WebSocket Realtime Bus]: authority:operations channel
```

---

## 3. Model Loading & Artifact Registry

The service initializes singleton artifacts at startup:
- **PyTorch Checkpoint**: `backend/app/ml/artifacts/v1.0.0/model.pt`
- **ONNX Computational Graph**: `backend/app/ml/artifacts/v1.0.0/model.onnx`
- **Preprocessing Scaler**: `backend/app/ml/artifacts/v1.0.0/scaler_config.json` & `scaler.joblib`
- **Threshold Calibration**: `backend/app/ml/artifacts/v1.0.0/threshold_config.json`
- **Metadata Manifest**: `backend/app/ml/artifacts/v1.0.0/metadata.json`

### Model Health States
- `MODEL_LOADING`: Initial state during startup or dynamic reload.
- `MODEL_READY`: Model, scaler, thresholds, and numerical smoke tests verified.
- `MODEL_DEGRADED`: Fallback runtime active (e.g. PyTorch fallback when ONNX fails).
- `MODEL_ERROR`: Artifacts missing or incompatible; inference skipped safely.
- `MODEL_DISABLED`: Inference administratively paused.

---

## 4. Preprocessing & Normalization Contract

Preprocessing strictly matches the Prompt 8 training and evaluation pipeline:
1. **Raw IMU Extraction**: Accel $(a_x, a_y, a_z)$ in $g$, Gyro $(g_x, g_y, g_z)$ in $\text{rad/s}$.
2. **Derived Magnitudes**:
   $$\text{accel\_mag} = \sqrt{a_x^2 + a_y^2 + a_z^2}$$
   $$\text{gyro\_mag} = \sqrt{g_x^2 + g_y^2 + g_z^2}$$
3. **Temporal Resampling**: `IMUResampler` linearly interpolates non-uniform or jittered sensor timestamps onto an exact 150-sample uniform grid (3.0s duration at 50 Hz).
4. **Robust Scaling**:
   $$X_{\text{scaled}} = \frac{X - \text{center}}{\text{scale}}$$
   where $\text{center} = \text{median}$ and $\text{scale} = \text{IQR} = Q_{75} - Q_{25}$ computed during offline normal activity training.

---

## 5. Anomaly Score Formula

The reconstruction error anomaly score is calculated using Mean Squared Error (MSE):
$$\text{Score} = \text{MSE}(X, \hat{X}) = \frac{1}{T \times D} \sum_{t=1}^{T} \sum_{d=1}^{D} \left( X_{t,d} - \hat{X}_{t,d} \right)^2$$
where $T = 150$ timesteps and $D = 8$ channels.

---

## 6. Temporal Persistence & Hysteresis State Machine

To eliminate transient sensor noise and prevent threshold oscillation (flapping):

```
                  +-----------------------------------+
                  |              NORMAL               |
                  +-----------------------------------+
                    │                               ▲
      Score >= 5.80 │                               │ Score < 4.93 (x2)
                    ▼                               │
                  +-----------------------------------+
                  |             CANDIDATE             |
                  +-----------------------------------+
                    │                               │
   Score >= 5.80    │                               │ Score < 4.93 (x1)
   (Consecutive x2) │                               │
                    ▼                               ▼
                  +-----------------------------------+
                  |             ANOMALOUS             |
                  +-----------------------------------+
                    │                               ▲
      Score < 4.93  │                               │ Score >= 5.80
      (Consecutive) │                               │
                    ▼                               │
                  +-----------------------------------+
                  |            RECOVERING             |
                  +-----------------------------------+
```

- **Primary Threshold ($T_{\text{anom}}$)**: $5.804714$ ($99^{\text{th}}$ percentile of validation reconstruction error)
- **Recovery Threshold ($T_{\text{recov}}$)**: $4.934007$
- **Hysteresis Deadband**: $[4.934007, 5.804714)$ — state remains unchanged to prevent rapid oscillation.
- **Persistence Requirement**: $N_{\text{persist}} = 2$ consecutive elevated windows required to enter `ANOMALOUS`.
- **Recovery Requirement**: $N_{\text{recovery}} = 2$ consecutive normal windows required to clear back to `NORMAL`.

---

## 7. Episode Deduplication & Event Contracts

### Single Episode Lifecycle
A continuous sensor anomaly produces a single `AnomalyEpisode` document with `anomaly_id = "anom_<uuid>"`. Subsequent anomalous windows update `peak_score`, `current_score`, `window_count`, and `duration_seconds`.

### Event Payloads

#### `anomaly.detected` (Broadcast to `authority:operations`)
```json
{
  "event_id": "evt_b1c2d3e4f5a6",
  "event_type": "anomaly.detected",
  "timestamp": "2026-08-21T16:20:00.000Z",
  "source": "lstm_inference_service",
  "version": 1,
  "payload": {
    "anomaly_id": "anom_7f8a9b0c1d2e",
    "tourist_id": "tourist_12345",
    "session_id": "sess_98765",
    "model_version": "v1.0.0",
    "timestamp": "2026-08-21T16:20:00.000Z",
    "window_start": "2026-08-21T16:19:57.000Z",
    "window_end": "2026-08-21T16:20:00.000Z",
    "anomaly_score": 6.8421,
    "threshold": 5.8047,
    "persistence_count": 2,
    "quality": {
      "overall_quality": "good",
      "gps_quality": "good",
      "imu_quality": "good",
      "observed_frequency_hz": 50.0,
      "completeness_ratio": 1.0
    },
    "last_known_gps": {
      "latitude": 10.2381,
      "longitude": 77.4892,
      "accuracy": 4.5
    },
    "source": "lstm_inference_service"
  }
}
```

#### `anomaly.cleared` (Broadcast to `authority:operations`)
```json
{
  "event_id": "evt_f1e2d3c4b5a6",
  "event_type": "anomaly.cleared",
  "timestamp": "2026-08-21T16:20:12.000Z",
  "source": "lstm_inference_service",
  "version": 1,
  "payload": {
    "anomaly_id": "anom_7f8a9b0c1d2e",
    "tourist_id": "tourist_12345",
    "session_id": "sess_98765",
    "model_version": "v1.0.0",
    "timestamp": "2026-08-21T16:20:12.000Z",
    "duration_seconds": 12.0,
    "peak_score": 7.4215,
    "recovery_score": 1.1240,
    "threshold": 5.8047,
    "source": "lstm_inference_service"
  }
}
```

---

## 8. Performance, Latency & Load Benchmarks

Empirical benchmark execution on local CPU (Python 3.14 + ONNX Runtime CPU Execution Provider):

| Metric Stage | Mean Latency | Median (p50) | 95th Percentile (p95) | 99th Percentile (p99) |
| :--- | :--- | :--- | :--- | :--- |
| **Preprocessing & Resampling** | 0.22 ms | 0.21 ms | 0.25 ms | 0.40 ms |
| **Model Inference (ONNX)** | 0.49 ms | 0.47 ms | 0.57 ms | 0.67 ms |
| **Postprocessing & Scoring** | 0.03 ms | 0.03 ms | 0.06 ms | 0.07 ms |
| **TOTAL Window Inference** | **0.75 ms** | **0.72 ms** | **0.91 ms** | **1.07 ms** |

- **Maximal Inference Throughput**: **473.1 windows / second**
- **Concurrency Test (10 Active Tourist Streams)**: 150 windows processed in 0.34s (442.4 win/s) with 0 errors.

---

## 9. Observability & REST Endpoints

1. `GET /api/v1/internal/ml/health`: Returns model health, version, latency percentiles, queue depth, throughput.
2. `POST /api/v1/internal/ml/infer-window`: Dev diagnostic endpoint for single-window evaluation.
3. `GET /api/v1/anomalies/active`: Authority command center active anomaly feed.
4. `GET /api/v1/anomalies/history`: Historical anomaly records with filtering.

---

## 10. Security & Non-Interference Isolation

- Model parameters, thresholds, and anomaly state decisions are owned strictly by the backend service.
- Clients cannot self-report or override anomaly states.
- Model failure or unavailable ML artifacts do not impede core telemetry ingestion, GPS tracking, or user authentication.
