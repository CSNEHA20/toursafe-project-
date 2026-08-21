# TourSafe Prompt 8: Architectural & Machine Learning Decisions

## 1. Semi-Supervised Anomaly Detection vs Supervised Activity Classification

### Decision
We rejected training a standard supervised classification model (e.g. `is_fall: bool` or `activity_class = [walking, falling, etc.]`) and instead engineered an **unsupervised LSTM Autoencoder** trained solely on normal human locomotion patterns.

### Rationale
1. **The Open-World Problem in Tourist Safety**: In real-world environments, anomalous kinematic events are rare, diverse, and unpredictable (e.g. slipping on ice, collapsing from heat exhaustion, being thrown from a scooter, vehicle collisions, stumbling on uneven stairs). A supervised classifier trained on limited artificial fall simulations suffers severe false negatives on unseen anomalous dynamics.
2. **Definition of Anomaly**: By modeling the latent probability density and temporal structure of normal Activities of Daily Living (ADLs), any significant deviation produces elevated reconstruction loss ($\text{MSE}$).
3. **Decoupled Decision Logic**: Anomaly score is an objective continuous measurement of deviation from normal locomotion, not a trigger for emergency dispatch. Downstream decision policies (implemented in Prompt 9) evaluate persistence, GPS velocity, and user confirmation.

---

## 2. Model Architecture: Stacked LSTM Autoencoder with Bottleneck Latent State

### Decision
We implemented a PyTorch-based stacked LSTM architecture:
- **Encoder**: $\text{Input}(150 \times 8) \to \text{LSTM}(64) \to \text{Dropout}(0.2) \to \text{LSTM}(32) \to \text{FC}(16) \to \text{Tanh} \to \text{Latent}(16)$.
- **Decoder**: $\text{Latent}(16) \to \text{Repeat}(150 \times 16) \to \text{LSTM}(32) \to \text{Dropout}(0.2) \to \text{LSTM}(64) \to \text{TimeDistributed FC}(8) \to \text{Output}(150 \times 8)$.

### Rationale
1. **Temporal Horizon**: 150 timesteps (3.0 seconds at 50 Hz) captures 2 to 3 complete gait cycles for walking/jogging and the entire multi-phase trajectory of a fall (pre-fall, freefall, impact, rest).
2. **Bottleneck Dimension (16)**: Compressing $150 \times 8 = 1200$ scalar inputs into a 16-dimensional latent vector enforces strict dimensionality reduction, preventing the network from trivial identity mapping while preserving dominant cyclical gait dynamics.
3. **Bidirectional vs Unidirectional**: Unidirectional LSTM was selected for production efficiency and exact streaming compatibility during windowed inference.

---

## 3. Normalization Strategy: TourSafe RobustScaler (Median & IQR)

### Decision
We implemented `TourSafeRobustScaler` which scales features using channel-wise median and Interquartile Range ($\text{IQR} = Q_{75} - Q_{25}$) rather than standard mean-variance scaling.

### Rationale
Extreme physical shocks (such as 6g to 8g impact spikes) skew mean and variance metrics, distorting normal feature coordinates. Median and IQR are mathematically robust to outliers, ensuring that normal gait dynamics remain well-conditioned in $[-2.0, +2.0]$ coordinate space.

---

## 4. Multi-Tier Anomaly Threshold Calibration

### Decision
We implemented multi-tier statistical thresholding calibrated on the 99th percentile and variance of normal validation sequences:
- **Normal / Low Risk**: $\text{Reconstruction Error} < \tau_{\text{warn}}$ ($P_{95}$)
- **Suspicious / Elevated**: $\tau_{\text{warn}} \le \text{Reconstruction Error} < \tau_{\text{crit}}$ ($P_{99}$)
- **Anomalous / Critical**: $\text{Reconstruction Error} \ge \tau_{\text{crit}}$ ($P_{99.5}$ or $\mu + 3\sigma$)

### Rationale
A binary trigger creates rigid alarm states with high false-alarm rates. Multi-tier thresholds allow downstream telemetry aggregators to track progressive anomaly escalation.

---

## 5. Dual Model Artifact Format (PyTorch + ONNX)

### Decision
Model artifacts are exported simultaneously as PyTorch state dictionaries (`model.pt`) and standardized ONNX graphs (`model.onnx`) with automated numerical parity verification.

### Rationale
- PyTorch provides full retraining, fine-tuning, and research flexibility.
- ONNX allows high-throughput, cross-platform inference with hardware acceleration (ONNXRuntime) across backend server clusters and future edge devices without requiring a full PyTorch runtime.
