# TourSafe Feature Specification: `features_v1`

## 1. Feature Channel Dictionary

| Channel Name | Source | Physical Unit | Transformation | Valid Physical Range | Missing Value Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `accel_x` | Smartphone Accelerometer X | $\text{g}$ ($9.80665\text{ m/s}^2$) | None (raw lateral axis) | $[-16.0, +16.0]\text{ g}$ | Linear interpolation if gap $< 250\text{ms}$; else reject |
| `accel_y` | Smartphone Accelerometer Y | $\text{g}$ | None (raw longitudinal axis) | $[-16.0, +16.0]\text{ g}$ | Linear interpolation if gap $< 250\text{ms}$; else reject |
| `accel_z` | Smartphone Accelerometer Z | $\text{g}$ | None (raw vertical axis) | $[-16.0, +16.0]\text{ g}$ | Linear interpolation if gap $< 250\text{ms}$; else reject |
| `gyro_x` | Smartphone Gyroscope X | $\text{rad/s}$ | None (pitch rate) | $[-35.0, +35.0]\text{ rad/s}$ | Linear interpolation if gap $< 250\text{ms}$; else reject |
| `gyro_y` | Smartphone Gyroscope Y | $\text{rad/s}$ | None (roll rate) | $[-35.0, +35.0]\text{ rad/s}$ | Linear interpolation if gap $< 250\text{ms}$; else reject |
| `gyro_z` | Smartphone Gyroscope Z | $\text{rad/s}$ | None (yaw rate) | $[-35.0, +35.0]\text{ rad/s}$ | Linear interpolation if gap $< 250\text{ms}$; else reject |
| `accel_mag`| Derived Vector Magnitude | $\text{g}$ | $\sqrt{a_x^2 + a_y^2 + a_z^2}$ | $[0.0, 28.0]\text{ g}$ | Computed deterministically from 3D vector |
| `gyro_mag` | Derived Vector Magnitude | $\text{rad/s}$ | $\sqrt{g_x^2 + g_y^2 + g_z^2}$ | $[0.0, 60.0]\text{ rad/s}$ | Computed deterministically from 3D vector |

---

## 2. Normalization & Scaler Parameters

- **Method**: TourSafe RobustScaler with channel-wise median centering and Interquartile Range scaling:
  $$x_{\text{scaled}} = \frac{x - \text{median}(x)}{\text{IQR}(x) + \epsilon}$$
- **Anti-Leakage Rule**: The scaler is fitted strictly on the `X_train` partition of the active dataset version. Validation and test sets use stored training parameters.
- **Persistence**: Scaler parameters are persisted in both binary `scaler.joblib` and human-readable `scaler_config.json` with channel names and scaling statistics.
