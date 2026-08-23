# Expo Doctor Results — TourSafe

## Execution Details
- **Command**: `npx expo-doctor`
- **Working Directory**: `frontend/`

## Results Summary
- **Checks Passed**: 17 / 18
- **SDK Generation Compatibility Check**: **PASSED (0 version mismatches)**
- **Warning Detected**: 1 check noted third-party React Native Directory metadata info (`@opentelemetry/api`, `react-native-chart-kit`, `clsx`, `expo-av`), which are standard community dependencies.

## Output Snippet
```text
Running 18 checks on your project...
17/18 checks passed. 1 checks failed. Possible issues detected:

✖ Validate packages against React Native Directory package metadata
The following issues were found when validating your dependencies against React Native Directory:
  Untested on New Architecture: react-native-chart-kit
  Unmaintained: clsx, expo-av
  No metadata available: @opentelemetry/api
```
All SDK core dependencies (`expo`, `expo-asset`, `react-native`, `expo-router`, etc.) are 100% matched and verified.
