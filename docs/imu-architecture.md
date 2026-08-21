# TourSafe Physical IMU Sensor Acquisition & Telemetry Architecture

> **SCOPE DECLARATION**:
> Prompt 6 implements the **Mobile IMU Physical Sensor Acquisition Foundation** (Accelerometer + Gyroscope, 50 Hz Target Pipeline, High-Precision Timestamp Synchronization, Sensor Quality Monitoring, and Bounded Telemetry Buffering).
> **Prompt 6 does NOT implement**: AI models, LSTM neural networks, TensorFlow/ONNX inference, anomaly scoring, automated fall detection, geo-fencing, SOS automation, or long-term high-frequency database persistence.

---

## 1. Sensor APIs & Hardware Abstraction
TourSafe interfaces directly with device hardware Micro-Electro-Mechanical Systems (MEMS) motion sensors via **Expo Sensors API (`expo-sensors`)** on Expo SDK 52.
- **Accelerometer**: Reads 3-axis linear acceleration including Earth gravity.
- **Gyroscope**: Reads 3-axis angular rotational velocity.
- **Architecture**: Sensor subscriptions are owned exclusively by `lib/sensors/` service adapters (`AccelerometerAdapter`, `GyroscopeAdapter`, `IMUController`), completely decoupled from UI components.

---

## 2. Accelerometer Collection
- **Physical Sensor**: Device 3-axis accelerometer.
- **Raw Channels**:
  - `x`: Lateral acceleration (g)
  - `y`: Longitudinal acceleration (g)
  - `z`: Vertical acceleration (g, nominal ~1.0g resting flat)
- **Units**: $g$ (Earth standard gravity, $1g \approx 9.80665 \text{ m/s}^2$).
- **Integrity Guarantee**: Raw $X, Y, Z$ channels are permanently preserved in their unmodified state for downstream feature engineering.
- **No Mock Fallback**: If physical sensor is unavailable (e.g. running on web browser), returns explicit `unavailable` status; never substitutes random or simulated data.

---

## 3. Gyroscope Collection
- **Physical Sensor**: Device 3-axis angular rate sensor.
- **Raw Channels**:
  - `x`: Pitch angular velocity ($\text{rad/s}$)
  - `y`: Roll angular velocity ($\text{rad/s}$)
  - `z`: Yaw angular velocity ($\text{rad/s}$)
- **Units**: Radians per second ($\text{rad/s}$).
- **Integrity Guarantee**: Raw rotational channels are preserved; handles hardware absence with explicit status reporting.

---

## 4. Target Sampling Frequency (50 Hz Target)
- **Target Sampling Interval**: `IMU_SAMPLE_INTERVAL_MS = 20` ($\approx 50 \text{ Hz}$).
- **Operating System Reality**: OS hardware event dispatchers (Android SensorManager, iOS CoreMotion) provide best-effort delivery. The delivered frequency varies based on CPU load, thermal throttling, and hardware timer precision.
- **Engineering Principle**: TourSafe never assumes nominal 50 Hz; it measures actual delivered frequency continuously.

---

## 5. Actual Sampling Measurement
The `IMUQualityEngine` measures true delivered frequency and inter-sample timing in real time:
$$\text{Observed Frequency (Hz)} = \frac{\text{Sample Count}}{\text{Elapsed Time (seconds)}}$$
Measured parameters tracked continuously:
- `observedFrequencyHz`: Measured overall rate of synchronized samples.
- `accelerometerFrequencyHz`: Measured callback frequency from accelerometer.
- `gyroscopeFrequencyHz`: Measured callback frequency from gyroscope.
- `averageIntervalMs`: Mean delta between consecutive samples.
- `minIntervalMs` / `maxIntervalMs`: Interval extrema.
- `jitterMs`: Population standard deviation ($\sigma$) of inter-sample delivery intervals.
- `sampleGapCount`: Count of inter-sample intervals exceeding $50\text{ ms}$ ($2.5\times$ target).

---

## 6. Timestamp Strategy
Every sample captures dual-domain temporal metadata:
1. **Monotonic Timestamp (`monotonic_timestamp_ms`)**: High-precision monotonic timer (`performance.now()`) invariant to system clock adjustments, leap seconds, or NTP time synchronization steps. Used for interval statistics, jitter calculation, and pairing proximity.
2. **Wall-Clock Timestamp (`timestamp`)**: UTC ISO 8601 string (`YYYY-MM-DDTHH:mm:ss.sssZ`) for distributed server correlation and cross-sensor multi-modal alignment (e.g. GPS + IMU).

---

## 7. Sensor Sequence Numbers
- Every sample carries a strictly monotonically increasing integer `sequence_number` ($1, 2, 3, \dots$).
- Bound to the active `IMUSession`.
- Sequence counters reset only upon creation of a new session.
- Downstream temporal windowing uses sequence numbers to guarantee strict temporal ordering without re-sorting.

---

## 8. Sensor Timestamp Synchronization
Accelerometer and gyroscope hardware events fire in separate asynchronous OS callback threads:
- **Challenge**: Accelerometer sample $A_i$ and gyroscope sample $G_j$ rarely share exact timestamps.
- **Solution (`IMUSynchronizer`)**:
  1. Receives asynchronous streams into bounded timestamp-ordered queues.
  2. Evaluates timestamp delta $\Delta t = |t_{\text{accel}} - t_{\text{gyro}}|$.
  3. Pairs samples when $\Delta t \le \text{SYNC\_TOLERANCE\_MS}$ ($25\text{ ms}$).
  4. Generates a canonical `IMUSample` with `is_synchronized: true` and recorded `sensor_timestamp_delta_ms`.
  5. Prunes orphaned samples exceeding $2\times$ tolerance to prevent queue growth and memory leaks.

---

## 9. Derived Kinematic Magnitudes
TourSafe computes rotation-invariant scalar Euclidean magnitudes while keeping all raw channels intact:
- **Acceleration Magnitude**:
  $$A_{\text{mag}} = \sqrt{a_x^2 + a_y^2 + a_z^2}$$
- **Angular Velocity Magnitude**:
  $$G_{\text{mag}} = \sqrt{g_x^2 + g_y^2 + g_z^2}$$
Reusable functions: `calculateAccelerationMagnitude(x, y, z)` and `calculateAngularVelocityMagnitude(x, y, z)`.

---

## 10. Sensor Quality Monitoring Engine
Classifies real-time sensor stream quality into five discrete states:
- **`excellent`**: $\ge 45\text{ Hz}$, jitter $\le 6\text{ ms}$, sync offset $\le 10\text{ ms}$.
- **`good`**: $\ge 35\text{ Hz}$, jitter $\le 15\text{ ms}$, sync offset $\le 25\text{ ms}$.
- **`degraded`**: $\ge 20\text{ Hz}$, elevated jitter or occasional delivery gaps.
- **`poor`**: $< 20\text{ Hz}$, frequent callback stalls or excessive mismatch.
- **`unavailable`**: Hardware sensor missing or permission denied.

Thresholds are centralized in `lib/sensors/config.ts`.

---

## 11. Bounded Local Sliding Window Buffer
- Implemented in `BoundedIMUBuffer`.
- In-memory circular sliding window with fixed capacity of **250 samples** ($5.0\text{ seconds}$ at $50\text{ Hz}$).
- Automatically discards oldest samples when capacity is reached (FIFO).
- Prevents React state re-render bottlenecks by isolating the 50 Hz high-frequency stream outside of React state.
- Exposes `exportDiagnosticSnapshot(durationSeconds)` for developer diagnostic extraction.

---

## 12. Realtime Transport Preparation
- Integrated with Prompt 4's full-duplex WebSocket client (`realtimeClient`).
- Event type: `telemetry.imu` (or `imu.sample`).
- Transmits canonical JSON payload including raw channels, derived magnitudes, sequence number, and quality metadata.
- **High-Frequency Policy**: Raw 50 Hz IMU telemetry is directed exclusively to the telemetry/AI processing pipeline. Raw 50 Hz feeds are NOT broadcast to authority dashboards.

---

## 13. Authentication & Security
- Every IMU stream transmission requires a valid JWT bearer token.
- Backend derives `user_id` and `tourist_id` from authenticated token claims.
- Client cannot spoof identity by submitting mismatched `tourist_id` in request body.

---

## 14. Device Identifier
- Telemetry streams associate with the application installation identifier (`device_id`).
- Strict privacy: No hardware serial numbers, IMEI, phone numbers, or MAC addresses are used.

---

## 15. Android Platform Specifics
- Uses `SensorManager.SENSOR_DELAY_GAME` ($\approx 20\text{ ms}$ interval) via Expo Sensors.
- Subject to Android Doze Mode and power management when screen is turned off.
- Sensor hardware timestamps report nanoseconds since system boot, converted to monotonic milliseconds.

---

## 16. iOS Platform Specifics
- Uses `CMMotionManager` via Expo Sensors.
- Target update interval set to $0.02\text{ s}$.
- Requires active foreground execution unless running within an approved audio/location background capability.

---

## 17. Background Sensor Capabilities & Limitations
| Platform | Foreground 50 Hz | Background Continuous 50 Hz | Notes |
|---|---|---|---|
| **Android** | Supported | Limited / Restricted | Requires Foreground Service with sticky notification and wake lock |
| **iOS** | Supported | Not Supported in Expo managed workflow | CoreMotion throttles/pauses background IMU without native CoreLocation linking |
| **Web** | Limited | Not Supported | Generic Sensor API restricted in background tabs |

*Native Module Migration Path*: For continuous 24/7 background 50 Hz collection in future enterprise phases, a custom native module linking Android `ForegroundService` with `PARTIAL_WAKE_LOCK` and iOS `CLLocationManager` background activity will be implemented.

---

## 18. Power & Battery Considerations
- Continuous 50 Hz sampling engages device CPU and sensor hubs.
- The `IMUController` strictly stops and unregisters listeners when tracking is stopped.
- Duplicate subscriptions are explicitly prevented by state guards.

---

## 19. Future Telemetry Storage Pipeline (Prompt 7)
Prompt 6 builds the real mobile acquisition and validation foundation. Prompt 7 will design the high-throughput server-side telemetry pipeline (Kafka / Redis Streams / TimescaleDB / Parquet temporal window storage).

---

## 20. Future LSTM & AI Integration (Prompt 8+)
The canonical `IMUSample` schema designed in Prompt 6 ($a_x, a_y, a_z, g_x, g_y, g_z, A_{\text{mag}}, G_{\text{mag}}$) provides the exact input tensor structure required for temporal sliding window batching ($128 \times 8$ tensors) in future offline-trained LSTM neural networks.
