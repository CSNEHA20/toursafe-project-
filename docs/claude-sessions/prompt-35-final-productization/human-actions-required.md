# Human Actions Required (Operations & Deployment Guide)

## 1. Post-Deployment Configuration Steps

1. **Production Environment Secrets**:
   - Verify that all environment variables are populated in the production secrets vault (Vault / AWS Secrets Manager / GCP Secret Manager):
     - `SECRET_KEY`: Production 256-bit JWT signing secret.
     - `DATABASE_URL`: PostgreSQL 16 + PostGIS production connection string.
     - `REDIS_URL`: Redis 7+ cluster URL with TLS authentication.
     - `COPILOT_OPENAI_API_KEY` or `GEMINI_API_KEY`: Production LLM API key for AI Copilot grounding.
     - `SMS_GATEWAY_API_KEY`: Verified government SMS broadcast gateway credentials.

2. **Database Migration & PostGIS Spatial Indexes**:
   - Run production migration scripts: `alembic upgrade head`.
   - Verify PostGIS spatial indexes (`GIST`) on `incidents.location` and `safety_zones.polygon_geometry`.

3. **Production Domain & SSL Certificates**:
   - Provision DNS records and TLS 1.3 certificates for:
     - `command.toursafe.gov.in` (Authority Command Center)
     - `api.toursafe.gov.in` (REST & WebSocket API Gateway)

4. **Mobile App Store Submissions**:
   - Submit Android `.aab` bundles to Google Play Console (Internal/Production Track).
   - Submit iOS `.ipa` builds to Apple App Store Connect / TestFlight.
