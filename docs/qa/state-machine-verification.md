# TourSafe QA — State Machine Verification & Safety Semantics
**Document Version:** 1.0.0  
**Test Suite:** `backend/tests/regression/test_safety_regression.py`  
**Status:** ✅ **VERIFIED (12/12 Tests Passing, Invariants Upheld)**

---

## 1. Safety State Machine Architecture

TourSafe enforces a deterministic finite state machine (FSM) governing traveler risk. Direct state jumps that violate hysteresis or safety gates are rejected.

```
                    ┌──────────────┐
                    │   UNKNOWN    │ (Initial State / Disconnected)
                    └──────┬───────┘
                           │ Baseline Telemetry Ingested
                           ▼
                    ┌──────────────┐
       ┌───────────>│    NORMAL    │<───────────┐
       │            └──────┬───────┘            │
       │                   │ Low Risk / Danger  │ Recovery / Safe
       │                   ▼                    │ Check-in Confirmed
       │            ┌──────────────┐            │
       │            │    WATCH     │────────────┤
       │            └──────┬───────┘            │
       │                   │ Elevated Risk      │
       │                   ▼                    │
       │            ┌──────────────┐            │
       │            │   ELEVATED   │────────────┤
       │            └──────┬───────┘            │
       │                   │ Persistent Risk    │
       │                   ▼                    │
       │            ┌──────────────┐            │
       │            │  INCIDENT_   │────────────┘
       │            │  CANDIDATE   │
       │            └──────┬───────┘
       │                   │ Multi-Cycle Corroboration
       │                   ▼
       │            ┌──────────────┐
       │            │   INCIDENT   │
       │            └──────┬───────┘
       │                   │ Authority Acknowledge & Resolve
       │                   ▼
       │            ┌──────────────┐
       └────────────│  RECOVERING  │
                    └──────────────┘
```

---

## 2. State Transition Rules & Gating

| From State | Trigger Condition | Target State | Permitted? | Test Reference |
| :--- | :--- | :--- | :---: | :--- |
| `UNKNOWN` | Safe GPS telemetry sample ingested | `NORMAL` | ✅ | `test_SM_01` |
| `NORMAL` | Anomaly score $\ge 0.50$ (1 window) | `WATCH` | ✅ | `test_SM_01` |
| `NORMAL` | Danger geofence entry signal | `ELEVATED` | ✅ | `test_SM_02` |
| `NORMAL` | Direct jump to `INCIDENT_CANDIDATE` | *Gated* | ❌ | State machine prevents skip |
| `ELEVATED` | Danger zone + persistent anomaly ($>3$ windows) | `INCIDENT_CANDIDATE` | ✅ | `test_SM_03` |
| `INCIDENT_CANDIDATE`| Second consecutive anomalous cycle | `INCIDENT` | ✅ | `test_SM_03` |
| `INCIDENT` | Authority Acknowledgment | `ACKNOWLEDGED` (Incident) | ✅ | `test_GP11` |
| `ACKNOWLEDGED` | Authority Resolution | `RESOLVED` (Incident) | ✅ | `test_GP12` |
| `INCIDENT` | Tourist confirms "I am Safe" check-in | `RECOVERING` $\rightarrow$ `NORMAL` | ✅ | `test_safety_engine.py` |

---

## 3. Core Safety Semantics & Invariants

### 3.1 "MISSING DATA $\ne$ SAFE"
- If telemetry feeds are interrupted or signal quality degrades, the system **never** assumes the tourist is safe.
- Missing GPS samples trigger sensor health advisories and preserve or escalate the current risk state until fresh verification occurs.
- Verified in `test_SEM_01` and `test_SEM_02`.

### 3.2 False-Positive Suppression & Corroboration
- A single isolated spike in LSTM anomaly score does **not** trigger an immediate emergency incident.
- Escalation to `INCIDENT` requires multi-signal corroboration:
  1. Spatial Context: Danger zone entry or route deviation.
  2. Temporal Persistence: Consecutive anomalous windows ($N \ge 3$).
  3. Signal Fusion: Fusion weights from Category A (IMU) + Category B (Geofence) + Category F (Context).
- Verified in `test_RF_01` (single weak signal does not trigger incident) and `test_RF_03` (progressive multi-signal escalation).

### 3.3 Incident Deduplication & Idempotency
- Repeated identical anomaly signals for the same tourist do **not** spawn multiple duplicate incident records in MongoDB.
- All subsequent alerts correlate to the active incident dossier until resolution.
- Verified in `test_DEDUP_01` (10 repeated anomaly signals stabilize into single incident) and `test_DEDUP_02` (query idempotency).
