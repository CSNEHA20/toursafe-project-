# Prompt 35 — Final B2G Productization, Frontend Integration, UX Polish & System Finalization

## Prompt Objective

Complete the final productization phase across all dimensions:
1. **Design System & B2G Visual Language**: Standardize typography, status badges, and color tokens (Deep Navy, Saffron, Emerald, Teal, Crimson). Remove all prototype/mock text.
2. **Iconography Standardization**: Eliminate `@expo/vector-icons` dependencies in favor of `lucide-react-native` to ensure seamless web rendering and zero hydration mismatches.
3. **Unified Gateway & Authentication**: Build a government-grade entry portal (`frontend/app/index.tsx`) with active session auto-detection, 3 role gateways (Authority Command, Tourist Companion, Field Responder), live subsystem status, and multi-role B2G login.
4. **Live Subsystem Wiring**: Ensure the frontend consumes the authentic TourSafe FastAPI backend and Supabase/WebSocket realtime infrastructure without artificial mocks or invented AI responses.
5. **Quality & Verification**: Execute the full backend test suite (510+ tests), frontend TypeScript type check (0 errors), and automated frontend unit tests (29 tests).
6. **Documentation & Release Artifacts**: Create `docs/product/*` documentation suite, update release manifests, changelog, and generate the full 22-file Prompt 35 session folder.
