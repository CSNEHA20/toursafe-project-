# TourSafe Telemetry Dataset Specification

## 1. Dataset Geometry & Temporal Parameters

- **Nominal Sampling Rate**: $50.0\text{ Hz}$ ($\Delta t = 20\text{ ms}$).
- **Temporal Window Duration**: $3.0\text{ seconds}$ ($150\text{ discrete time samples}$).
- **Window Stride**:
  - Training Normal: $1.0\text{ second}$ ($50\text{ samples}$, $66.7\%$ overlap).
  - Validation Normal: $1.5\text{ seconds}$ ($75\text{ samples}$, $50.0\%$ overlap).
  - Test Benchmark: $1.0\text{ second}$ ($50\text{ samples}$).
- **Completeness Threshold**: $\ge 60\%$ valid samples required per window ($90/150$).
- **Maximum Tolerable Time Gap**: $250\text{ ms}$ before window splitting.

---

## 2. Dataset Immutability & Persistence Format

Datasets are persisted in `.npz` compressed tensor format alongside a JSON metadata manifest:

- `X_train`: Tensor of shape $(N_{\text{train}}, 150, 8)$, Normal ADL sequences only.
- `X_val`: Tensor of shape $(N_{\text{val}}, 150, 8)$, Normal sequences from unseen validation subjects.
- `X_test`: Tensor of shape $(N_{\text{test}}, 150, 8)$, Normal + Anomalous benchmark sequences from holdout subjects.
- `y_test`: Binary labels ($0 = \text{Normal}$, $1 = \text{Anomaly}$).
- `manifest.json`: Full lineage, SHA-256 cryptographic checksum, split summaries, quality report, and baseline channel distributions.

---

## 3. Anti-Leakage Protocol

The dataset builder guarantees zero data leakage across train, val, and test splits:
1. **Subject-Wise Separation**: No subject ID appears in more than one partition.
2. **Session-Wise Separation**: Continuous sessions are strictly contained within a single partition.
3. **Temporal Disjointness**: No overlapping sliding windows cross split boundaries.
4. **Duplicate Window Prevention**: Exact tensor hash collision checks are enforced across partitions.
