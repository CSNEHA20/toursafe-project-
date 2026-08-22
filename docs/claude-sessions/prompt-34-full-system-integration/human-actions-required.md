# Prompt 34 — Human Actions Required

## 1. Required Pre-Production Actions for Operators
1. Provision production environment secrets in Secret Manager (`JWT_SECRET_KEY`, `MONGODB_URI`, `REDIS_URI`, `TWILIO_AUTH_TOKEN`, `GEMINI_API_KEY`).
2. Sign production mobile app builds using production enterprise keys and submit to App Store & Google Play Store.
3. Execute `init_admin.py` to create the initial Root Authority Administrator account for jurisdiction onboarding.
4. Register production webhook URLs with third-party service provider dashboards (Twilio, Expo, DigiLocker).
