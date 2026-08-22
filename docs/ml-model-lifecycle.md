# TourSafe Model Lifecycle & Governance

## 1. Formal Model State Machine

Every model artifact in TourSafe transitions through strict lifecycle states:

```
[TRAINED]
    │
    ▼
[VALIDATED] (Automated Validation Gate: Artifacts, Checksums, Smoke Tests)
    │
    ▼
[APPROVED]  (Explicit Human Operator Sign-Off & Lineage Review)
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
[STAGING]          [SHADOW]           [CANARY]
    │                  │                  │
    └──────────────────┼──────────────────┘
                       │
                       ▼ (Authorized Deployment Confirmation)
                  [PRODUCTION]
                       │
                       ▼ (Incident or Regression Mandated)
                 [ROLLED_BACK]
```

---

## 2. Model States & Transition Invariants

| State | Allowed Transitions | Invariants & Requirements |
| :--- | :--- | :--- |
| `TRAINED` | `VALIDATED`, `REJECTED`, `ARCHIVED` | Initial state upon training completion. Cannot run in production. |
| `VALIDATED`| `APPROVED`, `REJECTED`, `ARCHIVED` | Must pass checksum checks, metadata completeness, scaler fits, and ONNX smoke tests. |
| `APPROVED` | `STAGING`, `SHADOW`, `CANARY`, `PRODUCTION`, `ARCHIVED` | Requires explicit approver ID, timestamp, and justification. |
| `STAGING` | `SHADOW`, `CANARY`, `PRODUCTION`, `APPROVED` | Isolated testing in non-critical environments. |
| `SHADOW` | `CANARY`, `PRODUCTION`, `APPROVED` | Runs asynchronously on live telemetry. No safety impacts. |
| `CANARY` | `PRODUCTION`, `APPROVED` | Limited, auditable exposure to a subset of tourist sessions. |
| `PRODUCTION` | `ROLLED_BACK`, `ARCHIVED` | Authoritative active model resolving real-time inferences. |
| `ROLLED_BACK` | `APPROVED`, `ARCHIVED` | Preserved for auditing. Immediately reactivates previous model. |

---

## 3. Deployment & Rollback Governance

- **Atomic Pointer Updates**: Deploying a candidate model updates `is_production: True` on the candidate and atomically demotes the current production model.
- **Rollback Guarantee**: `rollback(target_model_version, reason, actor)` immediately restores the target version to production and logs full auditable timestamps and actor attribution.
