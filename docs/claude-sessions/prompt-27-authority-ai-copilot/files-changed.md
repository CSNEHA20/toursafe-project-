# Files Changed: Prompt 27

## Backend New Files
- `backend/app/models/copilot.py`
- `backend/app/schemas/copilot.py`
- `backend/app/services/copilot/__init__.py`
- `backend/app/services/copilot/llm_provider.py`
- `backend/app/services/copilot/rag_service.py`
- `backend/app/services/copilot/tools.py`
- `backend/app/services/copilot/tool_registry.py`
- `backend/app/services/copilot/action_manager.py`
- `backend/app/services/copilot/context_manager.py`
- `backend/app/services/copilot/audit_service.py`
- `backend/app/services/copilot/copilot_service.py`
- `backend/app/services/copilot/test_utils.py`
- `backend/app/routers/copilot.py`
- `backend/tests/test_copilot_engine.py`
- `backend/tests/test_copilot_tools.py`
- `backend/tests/test_copilot_rag_security.py`
- `backend/tests/test_copilot_actions_and_audit.py`

## Backend Modified Files
- `backend/app/core/config.py`: Added Copilot settings and LLM keys.
- `backend/app/main.py`: Registered `copilot_router` and startup index initialization.

## Frontend New Files
- `frontend/lib/copilotApi.ts`
- `frontend/components/admin/CopilotPanel.tsx`

## Frontend Modified Files
- `frontend/app/admin/(tabs)/dashboard.tsx`: Added AI Copilot button and modal overlay.

## Documentation Files
- `docs/ai-copilot-policy.md`
- `docs/ai-copilot-tools.md`
- `docs/ai-copilot-rag.md`
- `docs/ai-copilot-security.md`
- `docs/claude-sessions/prompt-27-authority-ai-copilot/*`
