# TourSafe Prompt 8: IMU Dataset Research & Biomechanical Kinematic Analysis

## 1. Executive Summary & Objective

The primary goal of Prompt 8 is to construct an outlier-resistant machine learning data pipeline and train an unsupervised **LSTM Autoencoder** for anomaly detection in wearable/smartphone IMU telemetry.

Rather than framing tourist safety as a rigid supervised activity classifier (which fails to generalize across unseen anomalies and diverse body morphologies), TourSafe models the manifold of **Normal Human Movement (ADLs)**. By learning temporal auto-associative representations of normal locomotion, the network produces higher reconstruction errors when presented with abnormal kinematics (e.g. falls, collisions, collapses, high-energy shocks).

---

## 2. Benchmark IMU Datasets Evaluated

### 2.1 MobiAct Dataset (v2.0)
- **Institution**: Biomedical Informatics and eHealth Laboratory, TEI of Crete, Greece.
- **Sensor Hardware**: Samsung Galaxy S3 smartphone placed in pants pocket.
- **Sensors Recorded**: 3D Accelerometer (LSM330DLC, $\pm 2g / \pm 8g / \pm 16g$), 3D Gyroscope (LSM330DLC, $\pm 250 / \pm 500 / \pm 2000^\circ/s$), 3D Orientation.
- **Sampling Frequency**: Nominal 200 Hz (with actual Android timing jitter).
- **Subjects**: 67 subjects (56 male, 11 female, ages 20–47, heights 160–192 cm, weights 50–120 kg).
- **Activities Recorded**:
  - **12 ADLs**: Walking (`WAL`), Jogging (`JOG`), Jumping (`JUM`), Stairs Ascent (`STU`), Stairs Descent (`STN`), Standing (`STD`), Sitting (`SCH`), Car Step-in (`CSI`), Car Step-out (`CSO`), etc.
  - **4 Fall Types**: Forward Fall (`FOL`), Backward Fall (`BSC`), Lateral Fall (`FKL`), Fall from Chair (`SDL`).
- **Key Takeaways for TourSafe**:
  - Validates that pocket-mounted smartphone IMU capturing $\pm 2g$ to $\pm 16g$ and angular rates up to $2000^\circ/s$ provides sufficient resolution for locomotion vs impact dynamics.
  - Highlights the need for uniform temporal resampling to resolve variable Android OS sampling intervals.

### 2.2 SisFall Dataset
- **Institution**: Universidad de Antioquia, Colombia.
- **Sensor Hardware**: Custom waist-worn device with 2 accelerometers (ADXL345 $\pm 16g$, MMA7455L $\pm 8g$) and 1 gyroscope (ITG3200 $\pm 2000^\circ/s$).
- **Sampling Frequency**: 200 Hz.
- **Subjects**: 38 subjects (23 young adults 19–30 yrs, 15 elderly adults 60–75 yrs).
- **Activities Recorded**:
  - **19 ADLs**: Walking, jogging, stumbling, gentle sitting, fast sitting, bending, walking upstairs/downstairs, getting in/out of car.
  - **15 Fall Types**: Slip falls, trip falls, lateral falls, loss of consciousness/collapse, fainting against a wall.
- **Key Takeaways for TourSafe**:
  - Elderly gait patterns exhibit higher variance and lower cadence, demonstrating the necessity of robust scaling (median & IQR) over standard z-score normalization.
  - Falls consistently show a three-phase physical trajectory: (1) Free-fall/weightless descent ($|a| < 0.5g$), (2) High-G ground impact ($|a| > 3.5g$ to $8g$), (3) Post-impact stillness or posture inversion.

### 2.3 UCI Human Activity Recognition (UCI HAR)
- **Institution**: Non-Linear Complex Systems Laboratory, Università degli Studi di Genova.
- **Sensor Hardware**: Samsung Galaxy S II waist-mounted.
- **Sampling Frequency**: 50 Hz.
- **Subjects**: 30 subjects (ages 19–48).
- **Activities**: 6 standard ADLs (Walking, Walking Upstairs, Walking Downstairs, Sitting, Standing, Lying).
- **Key Takeaways for TourSafe**:
  - 50 Hz represents the international standard Nyquist-Shannon sampling rate for human kinematics (human ambulatory motions rarely exceed 15–20 Hz in spectral content).
  - Validates 50 Hz as the ideal bandwidth for low-power mobile telemetry and server ingestion.

---

## 3. TourSafe Standardized Sensor Channel Definition

TourSafe ingests 6 raw IMU channels and derives 2 kinematic magnitude invariants:

| Channel Index | Identifier | Unit | Physical Description |
|---|---|---|---|
| 0 | `accel_x` | $g$ ($9.80665 m/s^2$) | Lateral linear acceleration |
| 1 | `accel_y` | $g$ | Longitudinal / vertical linear acceleration |
| 2 | `accel_z` | $g$ | Anteroposterior linear acceleration |
| 3 | `gyro_x` | $rad/s$ | Pitch angular velocity |
| 4 | `gyro_y` | $rad/s$ | Roll angular velocity |
| 5 | `gyro_z` | $rad/s$ | Yaw angular velocity |
| 6 | `accel_mag` | $g$ | L2 norm $\sqrt{a_x^2 + a_y^2 + a_z^2}$ |
| 7 | `gyro_mag` | $rad/s$ | L2 norm $\sqrt{\omega_x^2 + \omega_y^2 + \omega_z^2}$ |

### Rationale for Vector Magnitudes ($|a|$, $|\omega|$)
Device orientation relative to the body varies (pocket, handbag, handheld). Vector magnitudes provide coordinate-frame invariant energy measures that assist the LSTM Autoencoder in identifying total kinetic shock and rotational dynamics regardless of device rotation.

---

## 4. Sampling Frequency & Temporal Windowing Specifications

1. **Nominal Sampling Rate**: $50.0 \text{ Hz}$ ($\Delta t = 20 \text{ ms}$).
2. **Window Duration**: $3.0 \text{ seconds}$.
3. **Timesteps per Window**: $N = 3.0 \text{ s} \times 50.0 \text{ Hz} = 150 \text{ samples}$.
4. **Window Tensor Shape**: `(batch_size, 150, 8)`.
5. **Window Stride**:
   - Training: $1.0 \text{ s}$ ($50 \text{ samples}$, $66.7\%$ overlap) for dense temporal coverage.
   - Validation / Evaluation: $1.5 \text{ s}$ ($75 \text{ samples}$, $50\%$ overlap).
6. **Data Quality Criteria**:
   - Completeness ratio $\ge 0.60$ ($\ge 90 \text{ samples}$).
   - Maximum inter-sample time gap $\le 250 \text{ ms}$.
   - Timestamp strictly monotonic.

---

## 5. Anti-Leakage & Subject-Wise Partitioning Guarantees

To ensure genuine real-world generalization, data splitting is performed strictly **by Subject ID**:
- **Train Partition (70%)**: Only normal locomotion/ADLs from Train Subjects.
- **Validation Partition (15%)**: Only normal locomotion from unseen Validation Subjects (used for early stopping & threshold calibration).
- **Test Partition (15%)**: Mixed evaluation set containing unseen Normal and Anomalous movements from holdout Test Subjects.

**Zero Subject Overlap Invariant**:
$$\text{Subjects}_{\text{train}} \cap \text{Subjects}_{\text{val}} = \emptyset, \quad \text{Subjects}_{\text{train}} \cap \text{Subjects}_{\text{test}} = \emptyset, \quad \text{Subjects}_{\text{val}} \cap \text{Subjects}_{\text{test}} = \emptyset$$

Normalizer statistics ($\text{median}, \text{IQR}$) are fit **strictly** on $\text{X}_{\text{train}}$, ensuring zero data leakage into validation or testing sets.
