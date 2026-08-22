# TourSafe — Test Environment Documentation

> **Prompt 32 — Comprehensive QA, Testing and End-to-End System Validation**
> Generated: 2026-08-22

---

## 1. Overview

This document describes the TourSafe test environment: services, ports, databases,
queues, environment variables, test accounts, mock providers, and test data.

### Environment Parity

| Aspect | Development | Test (CI) | Staging | Production |
|--------|-------------|-----------|---------|------------|
| MongoDB | localhost:27017 | In-memory mock | Atlas M10 | Atlas M30+ |
| Redis | localhost:6379 | In-memory mock | Managed Redis | Managed Redis |
| Backend | localhost:8000 | pytest ASGI transport | staging-api | api.toursafe.dev |
| Frontend | Expo Dev Server | tsc + eslint | Expo EAS | Expo EAS |
| ML Model | Stub fixture | Stub fixture | Deployed ONNX | Deployed ONNX |
| Notifications | Mocked | Mocked | FCM sandbox | Live providers |
| LLM/AI | Mocked | Mocked | Gemini sandbox | Gemini prod |

---

## 2. Services and Ports

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI backend | 8000 | Main API, WebSocket |
| MongoDB | 27017 | Primary document store |
| Redis | 6379 | Realtime state, caching, queues |
| Expo Dev Server | 8081 | Mobile frontend |

In automated tests, FastAPI is exercised via httpx.AsyncClient with ASGITransport.
No live network port is required. MongoDB and Redis are mocked via in-memory Python classes.

---

## 3. Environment Variables (Test Values Only — No Real Secrets)

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=toursafe_test
JWT_SECRET=test-jwt-secret-not-for-production
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:8081
HOST=0.0.0.0
PORT=8000
DEBUG=True

# ML (fixture/stub — no live model in tests)
ML_MODEL_PATH=tests/fixtures/models/stub_lstm.onnx
ML_ENABLED=false

# Redis (mocked in unit tests — no real connection required)
REDIS_URL=redis://localhost:6379

# Notifications (ALL MOCKED — never call real providers in tests)
NOTIFICATION_PROVIDER=mock
FCM_SERVER_KEY=mock-fcm-key
TWILIO_ACCOUNT_SID=mock-sid
TWILIO_AUTH_TOKEN=mock-token
SENDGRID_API_KEY=mock-sendgrid-key

# AI Copilot (mocked)
GEMINI_API_KEY=mock-gemini-key
COPILOT_ENABLED=false
```

WARNING: Never commit real secrets to the repository.

---

## 4. Test Databases

| Database | Name | Purpose |
|----------|------|---------|
| Primary test DB | toursafe_test | Isolated from development toursafe |
| Unit tests | In-memory MockCollection | No real DB required |
| Integration tests | toursafe_test on localhost | Requires running MongoDB |
| E2E smoke tests | toursafe_test on localhost | Requires running MongoDB and Redis |

---

## 5. Test Queues

Redis queues used in the system:
- telemetry:ingest — raw telemetry ingestion
- safety:signals — safety signal fan-out
- notifications:send — notification dispatch
- incident:events — incident lifecycle events

In unit/integration tests, these are mocked using in-memory async queue classes.

---

## 6. Test Accounts

All synthetic test identities. No real PII. All deterministic.

| Role | ID | Email |
|------|----|-------|
| TOURIST | user_tourist_001 | tourist_qa@toursafe.test |
| TOURIST (secondary, IDOR target) | user_tourist_002 | tourist_qa2@toursafe.test |
| RESPONDER | user_responder_001 | responder_qa@toursafe.test |
| AUTHORITY_OPERATOR | user_auth_op_001 | auth_op_qa@toursafe.test |
| AUTHORITY_ADMIN | user_auth_admin_001 | auth_admin_qa@toursafe.test |
| SYSTEM_ADMIN | user_sys_admin_001 | sys_admin_qa@toursafe.test |
| PRIVACY_ADMIN | user_privacy_001 | privacy_qa@toursafe.test |
| AUDITOR | user_auditor_001 | auditor_qa@toursafe.test |
| AUTHORITY B (cross-jurisdiction) | user_auth_b_001 | auth_b_qa@toursafe.test |

---

## 7. Mock Providers

| Provider | Type | Tests |
|----------|------|-------|
| MockNotificationProvider | Python mock class | All notification tests |
| MockMLEngine | Python mock class | Non-LSTM tests |
| MockRedisClient | Python mock class | Redis-dependent tests |
| MockWebhookProvider | Python mock class | Webhook delivery tests |
| MockGeminiClient | Python mock class | AI copilot tests |
| MockSMSProvider | Python mock class | SMS notification tests |
| MockEmailProvider | Python mock class | Email notification tests |

WARNING: Mock success does NOT equal real provider success.

---

## 8. Test Data Strategy

- All test data is synthetic and deterministic.
- Test data uses @toursafe.test email domain (not a real domain).
- GPS coordinates use Goa, India fixtures: 15.2993N, 74.1240E.
- All timestamps use 2026-08-22T10:00:00Z as epoch.
- Test IDs are human-readable prefixed strings (e.g., tourist_qa_001).
- No random values without a seeded RNG.

---

## 9. Test Data Isolation

- Each test module uses its own MockDatabase instance or fresh fixture.
- autouse=True fixtures reset mock state before each test class.
- Real DB tests use toursafe_test, never toursafe.
- cleanup_test_data.py removes all test-prefixed documents after E2E runs.

---

## 10. Environment Parity Differences

| Difference | Development | Test | Impact |
|------------|-------------|------|--------|
| MongoDB | Real instance | In-memory mock | Aggregation pipeline coverage limited |
| Redis | Real instance | In-memory mock | TTL expiry testing requires real Redis |
| Notifications | Real/sandbox | Mock | Cannot validate real provider delivery |
| ML Model | Real ONNX | Stub fixture | Anomaly accuracy not validated |
| WebSockets | Real server | ASGI transport | Upgrade negotiation not tested |
| LLM | Real Gemini | Mock | Tool routing tested; generation quality not |

---

## 11. How to Run Tests

```bash
# Backend unit and integration tests
cd backend
python -m pytest tests/ -v

# Specific test suite
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_safety_e2e.py -v

# Regression suite
python -m pytest tests/regression/ -v

# E2E suite
python -m pytest tests/e2e/ -v

# Frontend type-check
cd frontend
npx tsc --noEmit

# Frontend lint
npx eslint .
```

---

## 12. Test Reset / Seed / Cleanup

```bash
# Seed test database (real MongoDB only)
cd backend
python tests/fixtures/seed_test_data.py

# Clean test database (safe - only touches toursafe_test)
python tests/fixtures/cleanup_test_data.py
```

cleanup_test_data.py refuses to run if MONGODB_DATABASE=toursafe.
