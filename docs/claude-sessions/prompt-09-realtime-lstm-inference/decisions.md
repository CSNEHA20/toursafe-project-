# Architecture Decisions — Prompt 9: Real-Time LSTM Inference Service

## Decision 1: Model Runtime — ONNX Runtime CPU Provider with PyTorch Fallback
- **Reason**: ONNX Runtime provides optimized C++ graph execution with single-thread threadpool affinity, yielding sub-millisecond execution times (~0.49 ms per 150x8 window) and low memory footprint compared to full PyTorch session overhead.
- **Alternatives**: Pure PyTorch runtime (`model.pt`), TorchScript JIT, TensorRT.
- **Why Selected**: ONNX graph was already parity-verified against PyTorch in Prompt 8 (`max_diff < 1e-4`). The fallback mechanism guarantees zero downtime if an ONNX environment issue arises.

## Decision 2: Asynchronous Bounded Inference Queue with Backpressure Protection
- **Reason**: Real-time telemetry ingestion operates on a tight 50 Hz arrival deadline. Blocking the ingestion loop for model inference risks socket backlog and client timeout.
- **Alternatives**: Inline synchronous inference in HTTP receive handler; Unbounded background task spawning (`asyncio.create_task` per window).
- **Why Selected**: A bounded queue (capacity 1000) isolates ingestion from inference latency spikes while preventing memory leaks under extreme load. Dropped windows are explicitly logged and tracked as `dropped_windows` rather than falsely classified as normal motion.

## Decision 3: Temporal Persistence & Hysteresis State Machine
- **Reason**: Single anomalous windows frequently occur due to benign physical artifacts (e.g. phone slipping in pocket, placing phone firmly on a table). Directly alarming on a single window produces excessive false alerts and threshold oscillation (flapping).
- **Alternatives**: Single-window instantaneous threshold comparison; Moving average score filtering.
- **Why Selected**: State machine (`NORMAL` <-> `CANDIDATE` <-> `ANOMALOUS` <-> `RECOVERING`) combined with a hysteresis deadband between $T_{\text{recovery}} = 4.934$ and $T_{\text{anom}} = 5.805$ provides smooth transitions and guarantees that anomalies persist across at least 2 consecutive windows (2+ seconds) before alarming.

## Decision 4: Episode Deduplication & State Management
- **Reason**: Sustained motion anomalies (e.g. violent shaking over 10 seconds) generate multiple consecutive sliding windows. Emitting separate alert events for each window floods authority dashboards.
- **Alternatives**: Emitting every window as an alert; Suppressing subsequent windows completely without duration tracking.
- **Why Selected**: A stateful `AnomalyEpisodeManager` maintains one active episode per tourist, continually updating `peak_score`, `duration_seconds`, and `window_count`, emitting `anomaly.detected` at inception and `anomaly.cleared` upon resolution.

## Decision 5: Non-Coupling of ML Anomaly to Emergency/SOS
- **Reason**: An anomalous sensor reconstruction error indicates unusual physical kinematics, not a confirmed life safety emergency.
- **Alternatives**: Automatically triggering an SOS alert or responder dispatch when score > threshold.
- **Why Selected**: Safety-critical isolation principle: The anomaly event is an intermediate AI signal to be evaluated by a future safety orchestration engine combining user confirmation, GPS geofencing, inactivity, and heart rate telemetry.
