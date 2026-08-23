# Root Cause Analysis — TourSafe Post-Prompt-35 Forensic Recovery

## Primary Diagnostic Blockers Identified

### 1. Web Bundler Failure: Native Module Resolution Crash
- **Location**: `frontend/components/RealMap.tsx` and `frontend/app/tourist/(tabs)/map.tsx`
- **Error**:
  ```text
  Error: Importing native-only module "react-native/Libraries/Utilities/codegenNativeCommands" on web from: frontend/node_modules/react-native-maps/lib/MapMarkerNativeComponent.js
  ```
- **Mechanism**:
  - `RealMap.tsx` utilized a dynamic `require('./RealMap.native')` expression within the component body. During static analysis, Metro bundler for Web resolved all `require` statements, traversing into `react-native-maps` and attempting to load `codegenNativeCommands` (which does not exist in `react-native-web`).
  - `frontend/app/tourist/(tabs)/map.tsx` directly imported `MapView, { Marker, Polygon, Circle, PROVIDER_DEFAULT } from "react-native-maps"` rather than delegating through the platform-abstracted `RealMap` component.

### 2. Missing Notification Asset
- **Location**: `frontend/app.json` line 46
- **Issue**: `app.json` declared `"icon": "./assets/notification-icon.png"`, but the `frontend/assets/` directory did not exist in the repository.

### 3. Dependency Version Mismatches in Expo SDK 52
- **Location**: `frontend/package.json`
- **Issue**:
  - `expo-asset` was specified as `^57.0.12` (incompatible major version for SDK 52, which expects `~11.0.5`).
  - `react-native` was pinned to `0.76.5` instead of `0.76.9`.

### 4. Broken Expo Router Hierarchy & Missing Layouts
- **Location**: `frontend/app/_layout.tsx`, `frontend/app/tourist/_layout.tsx`, `frontend/app/admin/_layout.tsx`
- **Issue**:
  - Root `_layout.tsx` declared individual child leaves (`auth/login`, `tourist/(tabs)`, `admin/(tabs)`) rather than top-level layout folders (`auth`, `admin`, `tourist`, `responder`, `dev`), which prevented navigation across sibling screens and omitted the responder stack.
  - `tourist/_layout.tsx` and `admin/_layout.tsx` wrapped the tabs in an outer `<Tabs>` component with a single hidden tab, blocking access to sibling screens like `onboarding.tsx` and `splash.tsx`.

### 5. Windows Python Backend CP1252 Unicode Encoding Error
- **Location**: `backend/app/main.py`
- **Error**: `UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-1: character maps to <undefined>`
- **Mechanism**: Printing emoji characters (`✅`, `⚠️`) during lifespan startup raised an unhandled encoding exception under Windows cp1252 console encoding.

### 6. Pydantic Settings CORS Origins Parsing
- **Location**: `backend/app/core/config.py` & `backend/.env`
- **Issue**: Pydantic-settings attempted `json.loads` on `cors_origins: list[str]`, causing an unhandled `SettingsError` when given unquoted comma-delimited strings in `.env`.
