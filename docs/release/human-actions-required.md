# TourSafe — Human Actions Required for Production Cutover

## 1. Mandatory Operator Actions (Prior to Live Production Cutover)

1. **Production Secret Provisioning**:
   - Provision production secrets (`JWT_SECRET_KEY`, `MONGODB_URI`, `REDIS_URI`, `TWILIO_AUTH_TOKEN`, `GEMINI_API_KEY`) via Kubernetes Secret Manager or HashiCorp Vault.
   - *Never commit production credentials into source control.*

2. **Apple Developer & Google Play Store Submission**:
   - Sign production mobile binaries with enterprise release keystores.
   - Submit for App Store & Play Store review with privacy policy URL and background location disclosure.

3. **Authority Jurisdiction Onboarding**:
   - Create initial Root Authority Admin accounts using the `init_admin.py` bootstrap script.
   - Configure local police and emergency medical dispatch boundaries (GeoJSON polygons).

4. **External Provider Webhook Endpoints Registration**:
   - Register production webhook listener URLs with Twilio, Expo Push, and DigiLocker KYC provider dashboards.
   - Set SHA-256 HMAC shared signing secrets.
