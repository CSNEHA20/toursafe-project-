# TourSafe — Production Rollback Runbook

## 1. Rollback Authority & Trigger Criteria
Rollback may be triggered immediately by the **Release Commander** without committee signoff if:
- SOS pipeline latency $> 1000\text{ms}$ or failure rate $> 0.1\%$.
- Any unhandled 5xx exception loop is detected in safety scoring or dispatch orchestration.
- Critical data corruption occurs during state machine transitions.

---

## 2. Fast Rollback Procedure (< 2 Minutes)

### Step 1: Immediate Ingress Traffic Reversion
Switch ingress routing back to the previous stable baseline (Blue cluster):
```bash
# Revert ingress service traffic weighting to 100% Blue
kubectl patch service toursafe-ingress -n toursafe-prod --type='json' \
  -p='[{"op": "replace", "path": "/spec/selector/version", "value": "v0.9.9-stable"}]'
```

### Step 2: Roll Back Kubernetes Deployment
```bash
# Undo rollout to restore previous replica set
kubectl rollout undo deployment/toursafe-backend -n toursafe-prod
kubectl rollout status deployment/toursafe-backend -n toursafe-prod
```

### Step 3: Database Point-In-Time Restoration (If Schema Mutated)
If collection mutations cause backward incompatibility:
```bash
# Execute disaster recovery restoration from verified pre-release snapshot
python scripts/backup_restore_drill.py --restore-snapshot=dr_drill_snapshot_pre_release.json.gz
```

---

## 3. Post-Rollback Validation
1. Verify `/health/ready` returns 200 OK on reverted baseline.
2. Confirm active WebSocket client reconnects and channels resubscribe.
3. Broadcast notification to on-call engineering team and log incident RCA.
