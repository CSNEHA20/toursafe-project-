============================================================
PROMPT 2 — ARCHITECTURAL DECISIONS
================================================

DECISION 1: Separate Tourist Model from User Model
- Reason: Prompt 1 already established User for authentication (JWT, passwords) and Tourist for profile data. We preserved this boundary. Tourist now has KYC, contact, and profile state fields added without touching authentication credentials.

DECISION 2: KYC as Separate Collection (kyc_documents)
- Reason: KYC documents are sensitive identity verifications. Storing as a separate collection linked by tourist_id allows document metadata (type, reference, status, timestamps) without embedding large reference data in the Tourist document. States are explicit: pending, submitted, verified, rejected.

DECISION 3: Medical Profile as Separate Collection (medical_profiles)
- Reason: Medical information is highly sensitive per the prompt requirements. Separating it from both User and Tourist ensures proper field-level access control. The MedicalProfile is linked via tourist_id and accessed only through dedicated endpoints (/tourists/me/medical).

DECISION 4: Emergency Contacts as Separate Collection (emergency_contacts)
- Reason: A tourist may have multiple emergency contacts. A separate collection with tourist_id linkage supports 1:N relationships. Priority uniqueness constraint prevents duplicate primary contacts. Ownership is enforced via tourist_id in query, not URL parameter.

DECISION 5: Itinerary as Separate Collection (itineraries)
- Reason: Itinerary data is trip-specific and should be persisted per tourist. The 1:N relationship (one itinerary per tourist, or multiple) is supported by tourist_id linkage. Status field tracks active/completed/cancelled states.

DECISION 6: Authority verification_status, license_number, organization_name are block-modified via PATCH
- Reason: These are administrative fields that must not be changeable by regular authority users. The PATCH /api/v1/authorities/me endpoint filters out these fields for non-admin roles. Only admin-level verification updates go through the dedicated /authority/me/verification endpoint.

DECISION 7: Priority uniqueness for emergency contacts
- Reason: The application design requires one primary emergency contact per tourist. Duplicate priorities are prevented at the API validation level. If a tourist sets a contact as priority=1, any existing contact with priority=1 is demoted to priority=2 or lower.

DECISION 8: File storage abstraction with local development backend
- Reason: Storing large document binaries in MongoDB is discouraged. A storage abstraction layer allows local file-based development while preparing for future S3-compatible object store replacement. The API returns document metadata (storage_key, url, status, mime_type) rather than exposing filesystem paths.

DECISION 9: JWT-derived user_id for all ownership enforcement
- Reason: The frontend should never trust tourist_id or user_id supplied by the client. All backend endpoints derive the authenticated user from the JWT token payload via the get_current_user dependency. The user_id from the JWT is used to query MongoDB, ensuring a tourist can only access their own data.

DECISION 10: Consistent API error structure
- Reason: Mobile clients need predictable error handling. All endpoints return {"error": {"code": "...", "message": "...", "details": {}}}. Stack traces are suppressed. Meaningful codes (PROFILE_NOT_FOUND, VALIDATION_ERROR, etc.) help clients handle errors appropriately without parsing technical details.

DECISION 11: MongoDB indexes for query performance
- Reason: Proper indexes ensure fast queries on large datasets. Key indexes: users.email (unique, for login), tourists.user_id (for profile lookup), authorities.user_id (for authority profile), emergency_contacts.tourist_id (for contact listing), itineraries.tourist_id (for itinerary listing), kyc_documents.tourist_id (for KYC status), medical_profiles.tourist_id (for medical data). Authority search fields indexed for directory pagination and search.

DECISION 12: Mock data preserved for non-migrated screens
- Reason: Per the real data rule (requirement 20), screens fully migrated to real APIs no longer use mockData.ts. However, mock data remains available for screens not yet migrated, with clear documentation of what remains mocked. This allows incremental migration without breaking the whole app.