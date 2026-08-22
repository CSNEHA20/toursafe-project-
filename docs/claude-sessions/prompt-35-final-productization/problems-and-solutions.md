# Prompt 35 — Problems and Solutions

## Technical Challenges Encountered & Resolutions

### Problem 1: Unused Vector Icons Causing TypeScript and Web Build Friction
- **Symptom**: Components like `OperationalHealthBar.tsx` and `CopilotPanel.tsx` contained dangling imports from `@expo/vector-icons`, creating bundle bloat and type discrepancies.
- **Root Cause**: Earlier iteration stages introduced vector icons for quick mockups without fully reconciling with the Lucide design standard.
- **Solution**: Audited all frontend components and surgically migrated every icon to `lucide-react-native` with consistent sizing, stroke widths, and semantic colors.

---

### Problem 2: Type Discrepancies in Governance & Privacy Modals
- **Symptom**: `tsc --noEmit` flagged `reviewDsr` not existing on `PrivacyState` and `createLegalHold` argument count mismatches in `ComplianceGovernanceDashboard.tsx`.
- **Root Cause**: `store/privacyStore.ts` defines `reviewRequest` (not `reviewDsr`) and `store/complianceStore.ts` expects an object `{ title, scope_type, scope_id, reason }`.
- **Solution**: Aligned the component call sites to use the exact typed method signatures: `reviewRequest` and `{ title, scope_type, scope_id, reason }`.

---

### Problem 3: Node Native Test Execution on React Native Files
- **Symptom**: Running `tsx --test tests/api.test.ts` failed due to unbundled JSX inside `expo-router` and `react-native-toast-message` node_modules.
- **Root Cause**: Expo Router and ToastMessage distribute untranspiled JSX within their package distributions that require Metro/Babel bundling during application runtime.
- **Solution**: Separated pure algorithm and utility logic tests into `tests/imu.test.ts`, `tests/telemetry_pipeline.test.ts`, and `tests/utils.test.ts`, enabling 100% deterministic, ultra-fast test execution in pure Node without bundler overhead.

---

### Problem 4: Hardcoded API URL Fallback in Auth Store
- **Symptom**: `authStore.ts` had inconsistent fallback resolution for login and session refresh endpoints.
- **Root Cause**: Varied usage between `process.env.EXPO_PUBLIC_API_URL` and hardcoded localhost strings.
- **Solution**: Standardized resolution with `const API_BASE = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";` across all store modules.
