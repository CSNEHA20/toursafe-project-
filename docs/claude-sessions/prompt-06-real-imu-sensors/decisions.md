# Prompt 6: Architectural Decisions

## Decision 1: Dedicated IMU Service Architecture vs Screen-Level Hooks
- **Decision**: Centralize all hardware subscriptions, timestamping, synchronization, quality calculations, and lifecycle within `frontend/lib/sensors/` service adapters (`AccelerometerAdapter`, `GyroscopeAdapter`, `IMUSynchronizer`, `IMUQualityEngine`, `BoundedIMUBuffer`, `IMUController`), completely decoupled from React screens.
- **Reason**: 50 Hz sensor callbacks (50 updates/second) cause severe UI thread frame drops and re-render thrashing if tied directly to React component render cycles.
- **Alternatives**: Hook-based `useAccelerometer()` inside components.
- **Why Selected**: Decoupling allows high-frequency sensor acquisition to run in background queues, updates the Zustand store at a throttled rate (~10 Hz), and preserves a clean 50 Hz bounded buffer for downstream temporal windowing.

---

## Decision 2: Timestamp Synchronization Tolerance Threshold (25 ms)
- **Decision**: Configure `IMU_CONFIG.SYNC_TOLERANCE_MS = 25` (ms) as the maximum allowable timestamp delta to pair an accelerometer sample with a gyroscope sample.
- **Reason**: At 50 Hz target frequency, nominal sample period is $20\text{ ms}$. Accelerometer and gyroscope callbacks are scheduled on separate OS hardware interrupt queues and rarely fire concurrently. A 25 ms tolerance ($1.25\times$ nominal interval) allows realistic inter-callback phase offset while guaranteeing that paired kinematic readings reflect virtually identical physical moments in time.
- **Alternatives**:
  1. $0\text{ ms}$ (exact timestamp match): Impossible on mobile OS hardware due to separate asynchronous interrupt threads.
  2. Blind combination of `latestAccel` and `latestGyro`: Creates temporal skew during rapid movements (e.g. slips, drops, or collisions).
- **Why Selected**: 25 ms is physically rigorous for human kinematics while robust against normal mobile OS callback jitter.

---

## Decision 3: Preserving Raw Sensor Channels Alongside Derived Magnitudes
- **Decision**: Always retain raw $a_x, a_y, a_z$ (g) and $g_x, g_y, g_z$ ($\text{rad/s}$) channels in the canonical `IMUSample` record, appending $A_{\text{mag}}$ and $G_{\text{mag}}$ as derived fields rather than replacing raw channels.
- **Reason**: Future deep learning models (such as 1D-CNNs and BiLSTMs) require directional coordinate channels to distinguish between specific multi-axis movement patterns (e.g. forward tripping vs backward falling vs walking). Scalar magnitude alone loses rotational orientation.
- **Alternatives**: Storing only magnitude scalars to reduce bandwidth.
- **Why Selected**: Preserves raw data integrity for full-fidelity model experimentation.

---

## Decision 4: Monotonic Timing vs Wall-Clock Timestamps
- **Decision**: Dual-timestamp strategy: Capture `monotonic_timestamp_ms` via `performance.now()` for interval calculation, jitter computation, and pairing; retain ISO 8601 UTC `timestamp` for distributed server correlation and cross-sensor alignment.
- **Reason**: Wall-clock time (`Date.now()`) is subject to NTP clock skew, system time adjustments, and leap seconds, which introduce artificial jitter spikes or negative intervals. Monotonic timers guarantee strictly non-decreasing inter-sample deltas.
- **Alternatives**: Using only ISO 8601 strings.
- **Why Selected**: Eliminates false jitter spikes while preserving global wall-clock synchronization.

---

## Decision 5: Bounded Circular In-Memory Buffer (250 Samples / 5.0 Seconds)
- **Decision**: Maintain a bounded sliding window of 250 samples in `BoundedIMUBuffer` rather than storing unlimited telemetry in global React state.
- **Reason**: At 50 Hz, 1 minute of telemetry generates 3,000 objects. Storing this in React state causes unbounded memory growth and garbage collection pauses. 250 samples ($5.0\text{ s}$) is ideal for temporal window slicing (e.g. 128-sample LSTM inference windows) and developer diagnostic snapshots.
- **Alternatives**: Unlimited array in Zustand store.
- **Why Selected**: Guarantees fixed $O(1)$ memory consumption and zero UI lag.
