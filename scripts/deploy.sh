#!/usr/bin/env bash
# TourSafe Automated Deployment Script
# Usage: ./scripts/deploy.sh [environment] [version_tag]

set -euo pipefail

ENV="${1:-staging}"
TAG="${2:-latest}"

echo "================================================================================"
echo "🚀 INITIATING TOURSAFE DEPLOYMENT"
echo "Environment: ${ENV}"
echo "Image Tag:   ${TAG}"
echo "Timestamp:   $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "================================================================================"

# Step 1: Pre-deployment Environment & Secrets Verification
echo "[STEP 1/5] Validating environment configuration..."
if [ "${ENV}" = "production" ]; then
    if [ -z "${JWT_SECRET:-}" ] || [ "${JWT_SECRET}" = "change-this-to-a-secure-random-string" ]; then
        echo "❌ ERROR: Production JWT_SECRET is not configured with high entropy."
        exit 1
    fi
fi

# Step 2: Database Schema Safe Migration
echo "[STEP 2/5] Checking and running forward database migrations..."
python scripts/migrate.py up

# Step 3: Container Deployment / Rolling Update
echo "[STEP 3/5] Applying container orchestration updates..."
if command -v kubectl &> /dev/null; then
    echo "Updating Kubernetes deployment image tags..."
    kubectl set image deployment/toursafe-api toursafe-api=toursafe/backend-api:"${TAG}" -n toursafe --record
    kubectl rollout status deployment/toursafe-api -n toursafe --timeout=180s
else
    echo "kubectl not detected. Falling back to docker compose rolling recreation..."
    docker compose -f docker-compose.yml up -d --no-deps --build backend
fi

# Step 4: Health Check & Probes Verification
echo "[STEP 4/5] Running health check verification..."
./scripts/health-check.sh "http://localhost:8000"

# Step 5: Post-Deployment Synthetic Smoke Test
echo "[STEP 5/5] Executing post-deployment synthetic smoke tests..."
python scripts/synthetic_smoke_test.py

echo "================================================================================"
echo "✅ TOURSAFE DEPLOYMENT COMPLETED SUCCESSFULLY"
echo "================================================================================"
