# Architecture & Technical Decisions — Prompt 16: ML Data Engineering & Model Lifecycle Platform

## 1. Immutable Dataset Versioning with Cryptographic SHA-256 Hashing

### Decision
Datasets are built as immutable `.npz` tensor archives containing explicit `X_train`, `X_val`, `X_test`, and `y_test` arrays, accompanied by a `manifest.json` containing SHA-256 bundle hashes and quality summaries. Overwriting an existing dataset version is rejected.

### Rationale
Reproducible machine learning requires exact lineage. Silent in-place mutation of training data leads to untraceable regression in anomaly detection thresholds and false-alarm characteristics.

---

## 2. Strict Subject-Wise Partitioning & Anti-Leakage Gate

### Decision
Datasets enforce strict subject-wise and session-wise separation between train, validation, and test splits. The `DataLeakageDetector` checks subject sets, session sets, and window tensor hashes, failing the build if any overlap is found.

### Rationale
Splitting adjacent temporal windows from the same continuous session across train and test leaks temporal dynamics and subject-specific biomechanical gait signatures, resulting in overly optimistic validation metrics that degrade in production.

---

## 3. Human-in-the-Loop Governance vs Automated Model Replacement

### Decision
We rejected automatic production replacement of models. A newly trained model initializes in the `TRAINED` state. Even if it scores higher on benchmark metrics, it must pass an automated validation gate, receive explicit human approval (`APPROVED`), undergo `STAGING` or `SHADOW` testing, and be promoted through an authorized deployment API.

### Rationale
In high-assurance tourist safety systems, automated model swaps introduce risk of catastrophic distribution failure on unmodeled edge cases. Explicit human review and shadow mode parity evaluation protect operational stability.

---

## 4. Population Stability Index (PSI) & Kolmogorov-Smirnov (KS) Feature Drift

### Decision
Input distribution monitoring utilizes Population Stability Index (PSI) across 10 quantile bins and two-sample Kolmogorov-Smirnov (KS) tests across all 8 IMU feature channels. Drift is classified into `NORMAL` ($\text{PSI} < 0.10$), `DRIFTING` ($0.10 \le \text{PSI} < 0.25$), and `CRITICAL` ($\text{PSI} \ge 0.25$).

### Rationale
PSI is mathematically robust for continuous feature distributions and provides intuitive threshold boundaries without requiring labeled ground truth.

---

## 5. Non-Blocking Asynchronous Shadow Mode

### Decision
Candidate models deployed to `SHADOW` mode execute asynchronously alongside the active production model in the background inference loop. Shadow predictions are recorded for statistical parity analysis but are completely isolated from the downstream Safety Orchestration Engine.

### Rationale
Shadow mode enables validation of candidate model performance, latency, and alert frequency on real tourist telemetry without risking false emergency alerts or safety disruption.
