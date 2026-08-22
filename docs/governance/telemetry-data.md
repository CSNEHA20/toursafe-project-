# TourSafe IMU Sensor & Telemetry Data Governance

**Scope:** Accelerometer, Gyroscope, Sliding Windows & Quality Metrics  

---

## 1. Data Processing Lifecycle & Distinctions

TourSafe clearly distinguishes between raw sensor signals and derived features:

* **Raw IMU Telemetry:** 50 Hz triaxial accelerometer $(a_x, a_y, a_z)$ and gyroscope $(g_x, g_y, g_z)$ streams captured directly from mobile device hardware.
* **Derived Window Features:** 3-second statistical aggregations (mean, standard deviation, energy, peak-to-peak amplitude, zero-crossing rate).
* **Anomaly Scores:** Reconstruction error computed by the LSTM autoencoder.
* **Safety State Transitions:** High-level operational events (`STABLE`, `MOTION_WARNING`, `CRASH_CONFIRMED`).

---

## 2. Retention Matrix

| Telemetry Layer | Storage Location | Retention Period | Deletion Behavior |
|---|---|---|---|
| **Raw IMU Vectors** | Redis Stream / MongoDB buffer | 30 Days | Automated hard delete via Retention Engine |
| **3-sec Aggregations** | MongoDB `telemetry_windows` | 90 Days | Hard delete |
| **Anomaly Events** | MongoDB `anomaly_events` | 180 Days | Archived if unlinked; preserved if incident-linked |
| **Safety Incident Telemetry** | MongoDB `incidents` | 730 Days | Legal Hold protection applies |

---

## 3. Privacy & Replay Defense

* Raw sensor payloads contain zero direct personal identifiers.
* Sequence numbering and monotonic timestamps protect against malicious packet replay.
* Battery-aware adaptive sampling reduces frequency during low power to preserve device health without violating tourist privacy.
