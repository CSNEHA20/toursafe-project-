# TourSafe Model Governance & Safety Policy

## 1. Core Governance Invariants

1. **Non-Automated Production Promotion**: Training scripts or automated evaluation pipelines are strictly prohibited from setting a model to `PRODUCTION` or `APPROVED`. All promotions require human authorization with recorded justification.
2. **Deterministic Safety Primacy**: Machine learning predictions are probabilistic signals. The downstream deterministic Safety Orchestration Engine (Prompt 11) is the sole authority for incident generation, responder dispatch, and SOS escalation.
3. **Safe Failure Behavior**: If an ML inference failure, out-of-bounds error, or model load failure occurs, the system records `model_error` and emits `ML_UNAVAILABLE`. It **never** fabricates a score or converts failures to `NORMAL`.
4. **Drift Non-Interference**: When Population Stability Index (PSI) indicates `DRIFTING` or `CRITICAL` input distribution shifts, the system notifies administrators and flags `RETRAINING_RECOMMENDED`. It never automatically alters decision thresholds or hot-swaps models.
5. **Durable Rollback Audit**: All rollbacks immediately restore prior validated model weights and record actor, timestamp, reason, previous version, and target version in immutable audit collections.

---

## 2. Role-Based Access Control (RBAC) Permissions

| Role | Allowed Actions | Description |
| :--- | :--- | :--- |
| `ML_VIEW` / `authority` | View models, metrics, datasets, drift reports, shadow parity | Operational visibility for authority command centers. |
| `ML_TRAIN` / `authority_admin` | Queue training jobs, build datasets, run validation gates | Technical operations and dataset curation. |
| `ML_APPROVE` / `lead_admin` | Sign-off model approvals, authorize staging/shadow mode | Quality assurance and compliance gating. |
| `ML_DEPLOY` / `system_admin` | Promote models to `PRODUCTION`, execute `CANARY` rollouts | High-privilege deployment authorization. |
| `ML_ROLLBACK` / `system_admin` | Trigger instant emergency rollback to prior version | Disaster recovery and incident mitigation. |
