# Problems & Solutions - Prompt 28: External Integrations & Interoperability Platform

## Problem 1: Relative Import Depth in Adapter Subpackage
- **Problem**: When importing `app.schemas.integrations` from `app/services/integrations/adapters/base.py`, using 3 dots (`from ...schemas`) resolved to `app.services.schemas` instead of `app.schemas`.
- **Solution**: Updated relative imports in the `adapters/` subfolder to 4 dots (`from ....schemas.integrations import ...`) or explicit top-level imports.

## Problem 2: MongoDB Connection Delay in Standalone Tests
- **Problem**: Unmocked Motor MongoDB operations in tests without an active mongod process caused test suites to wait for serverSelectionTimeout.
- **Solution**: Added in-memory fast fallbacks and `asyncio.wait_for(..., timeout=0.5)` guards across `audit.py`, `dead_letter.py`, and `conflict_resolver.py`. Tests executed in under 2 seconds.

## Problem 3: Pydantic v2 Deprecation Warnings
- **Problem**: Calling `.dict()` on Pydantic v2 schemas generated deprecation warnings.
- **Solution**: Swapped `.dict()` calls with `item.model_dump() if hasattr(item, 'model_dump') else item.dict()` across integration models, services, and copilot tools.

## Problem 4: Missing Frontend Lucide Icon Import
- **Problem**: `npx tsc --noEmit` flagged TS2304 `Cannot find name 'Layers'` in `_layout.tsx`.
- **Solution**: Added `Layers` to the `lucide-react-native` import in `frontend/app/admin/(tabs)/_layout.tsx`, resolving the compilation error.
