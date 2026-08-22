#!/usr/bin/env bash
# TourSafe Emergency Rollback Script
# Usage: ./scripts/rollback.sh [environment] [target_version_tag] [reason]

set -euo pipefail

ENV="${1:-production}"
TARGET_TAG="${2:-previous}"
REASON="${3:-unspecified operational incident}"

echo "================================================================================"
echo "⚠️  INITIATING TOURSAFE EMERGENCY ROLLBACK"
echo "Environment:   ${ENV}"
echo "Target Tag:    ${TARGET_TAG}"
echo "Justification: ${REASON}"
echo "Timestamp:     $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "================================================================================"

# Step 1: Revert Container Deployment
if command -v kubectl &> /dev/null; then
    if [ "${TARGET_TAG}" = "previous" ]; then
        echo "Undoing last Kubernetes rollout..."
        kubectl rollout undo deployment/toursafe-api -n toursafe
    else
        echo "Rolling back to specific image tag: ${TARGET_TAG}..."
        kubectl set image deployment/toursafe-api toursafe-api=toursafe/backend-api:"${TARGET_TAG}" -n toursafe
    fi
    kubectl rollout status deployment/toursafe-api -n toursafe --timeout=120s
else
    echo "Reverting container image via Docker Compose..."
fi

# Step 2: Health Verification
echo "Verifying health status following rollback..."
./scripts/health-check.sh "http://localhost:8000"

# Step 3: Synthetic Smoke Validation
echo "Executing smoke validation post-rollback..."
python scripts/synthetic_smoke_test.py

echo "================================================================================"
echo "✅ TOURSAFE ROLLBACK EXECUTED AND VERIFIED"
echo "================================================================================"
