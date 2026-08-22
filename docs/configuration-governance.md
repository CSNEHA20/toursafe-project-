# TourSafe — Configuration Governance & Policy Lifecycle

## 1. Unified Configuration Lifecycle Architecture

TourSafe implements a strict state machine for all safety-critical parameters, response policies, escalation matrices, notification channels, and system settings.

```
       ┌───────────┐
       │   DRAFT   │ <──── Edit Draft / Import
       └─────┬─────┘
             │ (validate_configuration)
             ▼
     ┌───────────────┐        Validation Errors
     │  VALIDATING   │ ───────────────────────────┐
     └───────┬───────┘                            │
             │ Valid                              │
             ▼                                    │
   ┌───────────────────┐                          │
   │ PENDING_APPROVAL  │                          │
   └─────────┬─────────┘                          │
             │                                    │
       ┌─────┴─────────────────────┐              │
       │ (approve_configuration)   │ (reject)     │
       ▼                           ▼              ▼
 ┌───────────┐               ┌───────────┐  ┌───────────┐
 │ APPROVED  │               │ REJECTED  │  │   DRAFT   │
 └─────┬─────┘               └───────────┘  └───────────┘
       │ (activate_configuration / rollback)
       ▼
  ┌──────────┐
  │  ACTIVE  │ ────► Runtime Engines & Redis Cache
  └────┬─────┘
       │ (superseded by new version or rollback)
       ▼
 ┌───────────┐
 │  RETIRED  │
 └───────────┘
```

---

## 2. Governance Lifecycle Stages

### 2.1 Draft Authoring (`DRAFT`)
- Administrators create draft configurations with semantic versioning (e.g. `v1.1.0`).
- Drafts are isolated in the database and have **zero impact** on active operational services.

### 2.2 Schema & Invariant Validation (`VALIDATING`)
Before approval, the validation engine checks:
- **Parameter Bounds**: Positive freshness limits, valid weights ($0.0 \le w \le 1.0$), ascending risk thresholds ($\text{watch} < \text{elevated} < \text{candidate} < \text{incident}$).
- **Escalation Cycle Detection**: Detects self-referencing stages and backward cycles.
- **Dependency Checks**: Confirms all referenced zones, policies, and channels exist.

### 2.3 Multi-Party Approval & Separation of Duties (`PENDING_APPROVAL` $\rightarrow$ `APPROVED`)
- **Separation of Duties**: To prevent rogue or mistaken policy activations, the author of a configuration (`created_by`) cannot approve their own configuration (`created_by != approved_by`).
- A distinct supervisor or authority administrator must review and sign off with a mandatory justification.
- Rejection preserves the draft with the reviewer's reasoning for iterative remediation.

### 2.4 Atomic Activation & Runtime Reconciliation (`ACTIVE`)
- Once approved, an administrator can promote the configuration to `ACTIVE`.
- The previously active configuration of the same type is atomically transitioned to `RETIRED`.
- **Cache Invalidation**: Redis caches (`toursafe:config:{type}:active`) are updated and stale keys purged.
- **Dynamic Hot-Reload**: Runtime services (`SafetyRulesConfig`, `ResponseOrchestrator`) update in-memory parameters dynamically.

### 2.5 Safe Rollback (`RETIRED` $\rightarrow$ `ACTIVE`)
- Authorized administrators can rollback the live environment to any previous approved or retired version.
- The rollback creates an atomic activation of the target version and records the change in the immutable audit log.
- Historical incidents and past decisions remain bound to their respective configuration versions.

---

## 3. Configuration Diffing & Cloning

- **Diff Engine**: Computes structured differences between any two versions (Version $N$ vs $N+1$), categorizing `added_keys`, `removed_keys`, and `modified_keys` with old/new values.
- **Cloning**: Clones any active or historical configuration into a new `DRAFT` for incremental tuning.

---

## 4. Safe Export & Draft-Only Import

- **Export**: Automatically scrubs sensitive infrastructure secrets, tokens, passwords, and API keys.
- **Import**: **Security Invariant**: All imported configurations are strictly forced to `DRAFT` status and must undergo the formal validation and multi-user approval workflow before production deployment.
