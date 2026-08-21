============================================================
PROMPT 2 — TOURIST & AUTHORITY DATA MANAGEMENT
============================================================

REAL TOURIST + AUTHORITY PROFILE MANAGEMENT
MEDICAL INFORMATION
EMERGENCY CONTACTS
TRAVEL ITINERARY
KYC / DOCUMENT METADATA

============================================================
IMPORTANT OPERATING RULE
============================================================

You are continuing development of the EXISTING TourSafe repository.

Prompt 1 has already implemented the backend foundation and authentication.

DO NOT rebuild Prompt 1.

DO NOT rewrite the authentication architecture.

DO NOT create mock implementations.

DO NOT use hardcoded tourist profiles.

DO NOT use hardcoded authority profiles.

DO NOT use frontend-only state as the source of truth.

All persistent TourSafe user information implemented in this prompt must be stored in MongoDB through the FastAPI backend.

The React Native application must consume the real backend APIs.

============================================================
1. TOURIST DATA MODEL
============================================================

Expand the Tourist profile into a real persistent TourSafe profile.

The Tourist entity should support the existing TourSafe frontend requirements.

Include appropriate fields for:
- Identity: tourist_id, user_id, full_name, date_of_birth/age, gender, nationality, passport_number or government identity reference, profile_photo_url
- Contact: email, phone, address, city, country
- KYC: kyc_status, identity_document_type, identity_document_reference, identity_verified_at
- Profile state: is_active, created_at, updated_at

Do not store unnecessary sensitive information.
Do not store raw passwords in the Tourist document.
Do not duplicate authentication credentials unnecessarily.
The User remains responsible for authentication.
Tourist remains responsible for tourist-specific profile information.

============================================================
2. TOURIST PROFILE API
============================================================

Create authenticated Tourist APIs.

At minimum:
- GET /api/v1/tourists/me
- PATCH /api/v1/tourists/me
- GET /api/v1/tourists/me/status

The authenticated user must only be able to modify their own tourist profile.
Do not accept arbitrary user_id from the frontend for self-service profile updates.
The backend must derive the authenticated user from the JWT.

============================================================
3. AUTHORITY PROFILE API
============================================================

Create:
- GET /api/v1/authorities/me
- PATCH /api/v1/authorities/me
- GET /api/v1/authorities/me/status

Authority users must only be able to modify their own profile.
Authority verification status must be controlled by authorized administrative functionality.
A normal authority user must NOT be able to change verification_status, license verification, or organization verification through their own profile update endpoint.

============================================================
4. KYC FOUNDATION
============================================================

Implement the KYC data foundation.

Do NOT pretend that blockchain verification exists yet.
Do NOT claim that a document is verified merely because it was uploaded.

Use explicit states: pending, submitted, verified, rejected

Create a KYC/document metadata model. Store:
- document_id
- tourist_id
- document_type
- document_reference
- status
- submitted_at
- verified_at
- rejection_reason where applicable

For now, create the backend structure for document metadata.
Do not implement blockchain verification yet.
Do not implement OCR yet.
Do not implement automated identity verification yet.

============================================================
5. FILE UPLOAD ARCHITECTURE
============================================================

Inspect the existing project and determine whether a file storage mechanism already exists.

Do NOT store large document binaries directly inside MongoDB unless there is a specific architectural reason.

Create a storage abstraction.
For development, it may use local storage or the existing configured storage mechanism.
The API should return document metadata rather than exposing arbitrary filesystem paths.
Do not expose private document storage publicly.
Prepare the architecture so a future S3-compatible object store can replace the development storage implementation.

============================================================
6. MEDICAL PROFILE
============================================================

Create a separate MedicalProfile entity associated with a Tourist.

Do not put all medical information directly inside User.

Include:
- medical_profile_id
- tourist_id
- blood_group
- allergies
- medical_conditions
- medications
- disability_information where voluntarily provided
- other_emergency_medical_notes
- updated_at

Treat this information as highly sensitive.

Do not expose medical information through normal public tourist endpoints.

============================================================
7. MEDICAL API
============================================================

Implement:
- GET /api/v1/tourists/me/medical
- PUT /api/v1/tourists/me/medical
- DELETE /api/v1/tourists/me/medical

Only the authenticated tourist can manage their own medical profile through these endpoints.
Do not yet implement emergency responder access.
Emergency access will be implemented later through the TourSafe Digital Identity / emergency authorization system.

============================================================
8. EMERGENCY CONTACTS
============================================================

Create an EmergencyContact entity.

Fields:
- emergency_contact_id
- tourist_id
- name
- relationship
- phone
- alternate_phone
- email
- priority
- created_at
- updated_at

A tourist may have multiple emergency contacts.

Support: create, read, update, delete

API:
- GET /api/v1/tourists/me/emergency-contacts
- POST /api/v1/tourists/me/emergency-contacts
- PATCH /api/v1/tourists/me/emergency-contacts/{contact_id}
- DELETE /api/v1/tourists/me/emergency-contacts/{contact_id}

The backend must verify ownership.
A tourist must not be able to manipulate another tourist's emergency contact by changing the ID in the URL.

============================================================
9. EMERGENCY CONTACT VALIDATION
============================================================

Validate: name, relationship, phone, email where provided
Prevent duplicate priorities if the application design requires one primary emergency contact.
If you choose a different rule, document the decision in decisions.md

============================================================
10. TRAVEL ITINERARY
============================================================

The existing frontend already contains: app/tourist/(tabs)/itinerary.tsx

Make the itinerary backed by real persistent data.

Create an Itinerary model. It should support:
- itinerary_id
- tourist_id
- title
- destination
- start_date
- end_date
- notes
- status
- created_at
- updated_at

Support itinerary entries where appropriate.

If the existing frontend requires more structure, inspect it before defining the schema.

Do not invent unnecessary complexity.

============================================================
11. ITINERARY API
============================================================

Implement:
- GET /api/v1/tourists/me/itinerary
- POST /api/v1/tourists/me/itinerary
- PATCH /api/v1/tourists/me/itinerary/{itinerary_id}
- DELETE /api/v1/tourists/me/itinerary/{itinerary_id}

Again: ownership must be enforced by the backend. Do not trust tourist_id supplied by the client.

============================================================
12. CONNECT EXISTING TOURIST PROFILE SCREEN
============================================================

Inspect: app/tourist/(tabs)/profile.tsx

Connect it to: GET /api/v1/tourists/me, PATCH /api/v1/tourists/me

The screen must display real MongoDB data.

When the tourist edits profile information:
Frontend → FastAPI → MongoDB → successful response → store/UI update

Do not update the UI optimistically and assume the backend succeeded.

Handle: loading, success, validation failure, network failure, unauthorized, server error

============================================================
13. CONNECT EXISTING MEDICAL INFORMATION UI
============================================================

Inspect the existing profile / digital identity / emergency-related screens.

Where medical information is currently represented as mock data:
replace the mock data with: GET /api/v1/tourists/me/medical

When edited: PUT /api/v1/tourists/me/medical

Do not expose mock blood groups or mock medical conditions as production data.

If the current screen doesn't yet provide editing UI, implement the minimum UI required to view and edit the actual data without redesigning the overall visual system.

============================================================
14. CONNECT EMERGENCY CONTACT UI
============================================================

Inspect the current Tourist Profile / Digital ID / SOS-related UI.

Where emergency contact information is currently mocked:
replace it with the real emergency-contact API.

Implement: loading state, empty state, add contact, edit contact, delete contact, error state

Do not duplicate contacts in frontend state. MongoDB is the source of truth.

============================================================
15. CONNECT ITINERARY SCREEN
============================================================

Inspect: app/tourist/(tabs)/itinerary.tsx

Replace mock itinerary data with real API data.

Implement: loading, empty itinerary, create, edit, delete, refresh

Keep the existing visual style. Do not redesign the entire screen.

============================================================
16. AUTHORITY TOURIST DIRECTORY
============================================================

The existing authority frontend contains: app/admin/(tabs)/tourists.tsx

Prepare the backend API required for authority-side tourist listing.

Create: GET /api/v1/authority/tourists

This endpoint must:
- require authority/admin role
- return persisted tourist profiles
- support pagination
- support search
- support basic status filtering

Do not expose sensitive medical information in the directory response.
The tourist list should contain only operationally appropriate fields:
tourist_id, name, nationality, current profile status, KYC status

Real live GPS information will be connected later.

============================================================
17. AUTHORITY TOURIST DETAIL
============================================================

Create: GET /api/v1/authority/tourists/{tourist_id}

This should return authorized profile information.

Do not include emergency medical information yet unless explicitly required by the existing authorization model.
Medical emergency access will be implemented later.

For now establish the secure authority-side tourist identity/profile retrieval mechanism.

============================================================
18. AUTHORITY PROFILE SCREEN
============================================================

Inspect: app/admin/(tabs)/settings.tsx and any authority profile components.

Connect authority profile information to: GET /api/v1/authorities/me, PATCH /api/v1/authorities/me

Display: name, organization, designation, phone, office phone, address, license number, verification status

Do not allow the authority to modify verification status.

============================================================
19. REAL DATA RULE
============================================================

After this prompt:

The following must NOT be sourced from mockData.ts for authenticated users:
- Tourist profile
- Medical information
- Emergency contacts
- Itinerary
- Authority profile
- Tourist directory

These must come from FastAPI + MongoDB.

Mock mode may continue to exist for screens not yet migrated.

Clearly document what remains mocked.

============================================================
20. API ERROR CONTRACT
============================================================

Establish a consistent API error structure.

Use a predictable structure such as:
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}

Do not expose stack traces to the mobile application.
Use meaningful error codes.

Examples:
- PROFILE_NOT_FOUND
- VALIDATION_ERROR
- UNAUTHORIZED
- FORBIDDEN
- RESOURCE_NOT_FOUND
- DUPLICATE_RESOURCE
- DOCUMENT_REJECTED

Document the error contract.

============================================================
21. DATABASE INDEXES
============================================================

Create appropriate MongoDB indexes.

At minimum consider:
- users.email
- tourists.user_id
- authorities.user_id
- emergency_contacts.tourist_id
- itineraries.tourist_id
- kyc_documents.tourist_id
- medical_profiles.tourist_id

authority tourist search fields where appropriate

Do not blindly index every field.

Document the reasoning for important indexes.

============================================================
22. SECURITY
============================================================

Sensitive profile data must not be exposed unnecessarily.

Implement:
- ownership checks
- role checks
- input validation
- response models
- field filtering

Do not return:
- password_hash
- refresh token hashes
- internal database metadata
- private storage paths

Do not log:
- passwords
- JWT secrets
- medical information
- identity document contents

Do not place sensitive information into console.log statements.

============================================================
23. TESTING
============================================================

Create backend tests for:
- Tourist: get profile, update profile, unauthorized profile access, invalid profile data
- Medical: create, update, retrieve, delete, unauthorized access
- Emergency contacts: create, list, update, delete, ownership violation
- Itinerary: create, retrieve, update, delete, ownership violation
- KYC: submit metadata, retrieve status, authority/admin verification state
- Authority: get own profile, update own profile, unauthorized verification modification, authority tourist listing, authority tourist detail access
- Also test pagination and search for the authority tourist directory.

============================================================
24. FRONTEND TESTING
============================================================

Verify the existing screens against the real API.

At minimum test:
- Tourist: Profile, Medical information, Emergency contacts, Itinerary
- Authority: Profile/settings, Tourist directory, Tourist details

Verify: loading state, empty state, success state, validation error, network error, 401, 403

Do not leave screens showing stale mock data after successful API retrieval.

============================================================
25. DO NOT IMPLEMENT FUTURE SYSTEMS
============================================================

Do NOT implement:
- AI anomaly detection
- LSTM
- TensorFlow
- ONNX
- accelerometer
- gyroscope
- telemetry
- 50 Hz sensor streaming
- GPS streaming
- background GPS
- geo-fencing
- Redis live GPS
- Socket.IO live incidents
- blockchain
- Polygon
- DID
- IPFS
- dynamic QR emergency access
- e-FIR automation
- nearest responder routing
- FCM emergency dispatch

Those are intentionally separate future prompts.

============================================================
26. DOCUMENTATION REQUIREMENT
============================================================

Update: docs/claude-sessions/README.md

Add: Prompt 2 — Tourist & Authority Data Management
Status: Completed / Partially Completed

Also create:
docs/claude-sessions/prompt-02-tourist-authority-profiles/prompt.md
Copy the complete prompt into it.

Create: work-done.md
Write only what was actually implemented.

Create: files-changed.md
List every changed file.

Create: verification.md
Record actual commands and results.

Create: decisions.md
Record architectural decisions.

============================================================
27. UPDATE MAIN DOCUMENTATION
============================================================

Update the project's main README if necessary.

Document:
- backend startup
- MongoDB configuration
- authentication
- tourist profile API
- authority profile API
- medical profile API
- emergency contact API
- itinerary API
- authority tourist API

Clearly mark features that are not yet implemented.

============================================================
28. VALIDATION
============================================================

Before declaring this prompt complete:

Run backend tests.

Run frontend type-check.

Run frontend lint.

Start MongoDB.

Start FastAPI.

Start Expo.

Test:
- Tourist registration
- Tourist login
- Tourist profile retrieval
- Tourist profile update
- Medical profile
- Emergency contacts
- Itinerary
- Authority login
- Authority profile
- Authority tourist directory
- Authority tourist details

Verify actual records exist in MongoDB.

Verify frontend data comes from the backend.

Verify no migrated screen is silently using mockData.ts.

Fix all errors you encounter.

============================================================
29. FINAL RESPONSE
============================================================

At the end, provide:

IMPLEMENTED:
- exact features completed

FILES CREATED:
- list

FILES MODIFIED:
- list

API ENDPOINTS:
- list

DATABASE COLLECTIONS:
- list

SECURITY:
- list

TESTS:
- exact results

TYPE CHECK:
- result

LINT:
- result

MANUAL VERIFICATION:
- result

MOCK DATA STILL REMAINING:
- exact screens/features that still use mock data

DOCUMENTATION:
- session documentation files created

UNRESOLVED:
- exact remaining issues