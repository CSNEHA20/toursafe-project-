# Files Created and Modified — Prompt 31

## 1. Backend Core & Models
- `backend/app/models/compliance.py` (NEW)
- `backend/app/schemas/compliance.py` (NEW)
- `backend/app/core/compliance/minimization.py` (NEW)

## 2. Backend Compliance Services
- `backend/app/services/compliance/legal_hold_service.py` (NEW)
- `backend/app/services/compliance/retention_service.py` (NEW)
- `backend/app/services/compliance/consent_service.py` (NEW)
- `backend/app/services/compliance/privacy_request_service.py` (NEW)
- `backend/app/services/compliance/vendor_governance_service.py` (NEW)
- `backend/app/services/compliance/access_governance_service.py` (NEW)
- `backend/app/services/compliance/compliance_registry_service.py` (NEW)
- `backend/app/services/compliance/auditor_service.py` (NEW)
- `backend/app/services/compliance/__init__.py` (NEW)

## 3. Backend Routers & Wiring
- `backend/app/routers/compliance.py` (NEW)
- `backend/app/routers/privacy.py` (NEW)
- `backend/app/main.py` (MODIFIED)

## 4. Tests
- `backend/tests/test_compliance_and_governance.py` (NEW)

## 5. Frontend Types, Stores & Components
- `frontend/types/compliance.ts` (NEW)
- `frontend/types/privacy.ts` (NEW)
- `frontend/types/index.ts` (MODIFIED)
- `frontend/store/complianceStore.ts` (NEW)
- `frontend/store/privacyStore.ts` (NEW)
- `frontend/components/tourist/PrivacyConsentCenterModal.tsx` (NEW)
- `frontend/components/admin/ComplianceGovernanceDashboard.tsx` (NEW)
- `frontend/app/tourist/(tabs)/profile.tsx` (MODIFIED)
- `frontend/app/admin/(tabs)/settings.tsx` (MODIFIED)

## 6. Documentation
- `docs/governance/data-inventory.md` (NEW)
- `docs/governance/records-of-processing.md` (NEW)
- `docs/governance/ai-governance.md` (NEW)
- `docs/governance/location-data.md` (NEW)
- `docs/governance/telemetry-data.md` (NEW)
- `docs/governance/kyc-data.md` (NEW)
- `docs/governance/incident-data.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/prompt.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/work-done.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/files-changed.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/verification.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/decisions.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/problems-and-solutions.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/data-governance-findings.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/compliance-gaps.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/privacy-findings.md` (NEW)
- `docs/claude-sessions/prompt-31-compliance-governance/agent-response.md` (NEW)
- `docs/claude-sessions/README.md` (MODIFIED)
