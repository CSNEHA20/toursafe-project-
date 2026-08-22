# TourSafe Mobile Application Build & Release Pipeline

The TourSafe mobile application is built using React Native and Expo, supporting cross-platform Android and iOS releases.

## Build Profiles & EAS Configuration (`frontend/eas.json`)

| Profile | Target Distribution | Environment Flags | Output Artifact | Signing & Certificates |
| :--- | :--- | :--- | :--- | :--- |
| **development** | Expo Go / Internal Dev Client | `EXPO_PUBLIC_DEV_BYPASS=true`<br>`EXPO_PUBLIC_USE_MOCK=true` | Dev APK / Simulator Build | Expo Managed Debug Keystore |
| **preview** | Internal QA & Staging | `EXPO_PUBLIC_DEV_BYPASS=false`<br>`EXPO_PUBLIC_API_URL=staging-api` | Standalone APK / TestFlight Beta | Staging Keystore / Ad-Hoc Provisioning |
| **production** | Google Play Store & Apple App Store | `EXPO_PUBLIC_DEV_BYPASS=false`<br>`EXPO_PUBLIC_API_URL=prod-api` | Android App Bundle (AAB) / iOS IPA | Production Release Keystore / Distribution Cert |

---

## Secure Mobile Release Guidelines

1. **Client-Side Secret Protection**:
   - Mobile application bundles must **NEVER** contain sensitive service role keys, master database passwords, or private encryption keys.
   - Only public client keys (`EXPO_PUBLIC_SUPABASE_ANON_KEY`) and HTTPS/WSS API endpoints are embedded in client bundles.
2. **Background Sensor Collection & Offline Buffering**:
   - Production builds enable persistent background GPS location and IMU telemetry collection with OS foreground notification banners.
   - Telemetry batches are persisted to SQLite/AsyncStorage when offline and synchronized automatically upon network restoration.
3. **Automated EAS Build Execution**:
```bash
# Build Android App Bundle for Production Release
eas build --platform android --profile production --non-interactive

# Build iOS IPA for App Store Release
eas build --platform ios --profile production --non-interactive

# Submit Android AAB to Google Play Internal Track
eas submit --platform android --profile production
```
