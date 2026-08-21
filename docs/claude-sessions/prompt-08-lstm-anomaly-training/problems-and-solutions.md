# TourSafe Prompt 8: Problems Encountered & Technical Solutions

## 1. Non-Uniform Sampling and Mobile Timer Jitter

### Problem
Raw smartphone/wearable accelerometer and gyroscope sensors do not deliver samples at perfectly uniform 20.0 ms intervals due to OS scheduling interruptions, sensor thread priority, and battery throttling. Feeding irregular time intervals directly into an LSTM network violates the assumption of constant $\Delta t$, degrading temporal sequence modeling.

### Solution
We designed `IMUResampler` using SciPy's 1D linear interpolator with boundary clamping. The resampler maps non-uniform timestamps onto an exact 50.0 Hz grid (150 samples per 3.0 seconds). It also enforces a maximum allowable inter-sample gap rule ($\Delta t_{\max} \le 250\text{ ms}$), automatically rejecting windows with missing sensor blocks rather than interpolating across large data holes.

---

## 2. Preventing Subject-Wise Data Leakage

### Problem
In Human Activity Recognition and anomaly detection, random window shuffling across a combined dataset leads to extreme data leakage (optimistic bias), because windows from the same subject trial share identical sensor placement, body mass, and cadence characteristics across train and test sets.

### Solution
We implemented strict **Subject-Wise Group Partitioning** in `DatasetBuilder`:
1. The synthetic cohort is divided into non-overlapping subject sets: 14 Train Subjects, 3 Validation Subjects, and 4 Test Subjects.
2. An assertion verifies that the intersection of subject IDs between any two splits is strictly empty ($\emptyset$).
3. The `TourSafeRobustScaler` is fitted exclusively on the Train split, preventing test distribution leakage.

---

## 3. PyTorch 2.x ONNX Export Exporter Compatibility

### Problem
In PyTorch 2.13+, `torch.onnx.export` defaults to the Dynamo-based exporter, which requires the optional `onnxscript` package. In environments where `onnxscript` is not installed, the export fails with `ModuleNotFoundError: No module named 'onnxscript'`.

### Solution
We configured `dynamo=False` in `torch.onnx.export` to utilize the standard TorchScript-based ONNX exporter with opset version 14 and dynamic batch axes (`imu_window: {0: 'batch_size'}`). We also added an automated parity validation check in `ModelArtifactManager.verify_onnx_parity()` that tests input tensors through both PyTorch and ONNXRuntime, ensuring max absolute difference is $< 10^{-4}$.

---

## 4. Normalization Invariance to High-G Shocks

### Problem
Standard z-score normalization ($\mu, \sigma$) computed over windows containing high-G falls ($>6g$) severely skews the mean and variance, causing normal walking cycles to be compressed into tiny dynamic ranges.

### Solution
We engineered `TourSafeRobustScaler` to utilize median and interquartile range ($IQR = Q_{75} - Q_{25}$), fit solely on normal movement sequences. This keeps normal locomotion oscillations in the optimal $[-2, +2]$ range while allowing abnormal shocks to cleanly stand out in magnitude.
