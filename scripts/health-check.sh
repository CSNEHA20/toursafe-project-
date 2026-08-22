#!/usr/bin/env bash
# TourSafe Health Check Script
# Usage: ./scripts/health-check.sh [base_url]

BASE_URL="${1:-http://localhost:8000}"

echo "Checking TourSafe Liveness Probe (${BASE_URL}/health/live)..."
curl -sSf "${BASE_URL}/health/live" > /dev/null || { echo "❌ Liveness probe failed"; exit 1; }
echo "  [OK] Liveness probe returned 200 OK"

echo "Checking TourSafe Readiness Probe (${BASE_URL}/health/ready)..."
curl -sSf "${BASE_URL}/health/ready" > /dev/null || { echo "❌ Readiness probe failed"; exit 1; }
echo "  [OK] Readiness probe returned 200 OK"

echo "Checking TourSafe General Health Endpoint (${BASE_URL}/health)..."
curl -sSf "${BASE_URL}/health" > /dev/null || { echo "❌ General health check failed"; exit 1; }
echo "  [OK] General health endpoint healthy"

echo "All health probes successfully verified."
