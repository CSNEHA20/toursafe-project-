import pymongo
from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

client = AsyncIOMotorClient(settings.mongodb_uri)
database = client[settings.mongodb_database]


def get_database():
    return database


async def close_database():
    client.close()


async def init_db_indexes(db=None):
    """
    Initialize indexes for collections including 2dsphere geospatial indexes.
    """
    if db is None:
        db = database

    try:
        # Zones collection indexes
        # 1. Unique index on id and zone_id
        await db.zones.create_index("id", unique=True, sparse=True)
        await db.zones.create_index("zone_id", sparse=True)
        # 2. Geospatial 2dsphere indexes for boundary and center
        await db.zones.create_index([("boundary", "2dsphere")])
        await db.zones.create_index([("center", "2dsphere")])
        # 3. Filtering and searching indexes
        await db.zones.create_index([("status", pymongo.ASCENDING), ("is_active", pymongo.ASCENDING)])
        await db.zones.create_index([("zone_type", pymongo.ASCENDING)])
        await db.zones.create_index([("risk_level", pymongo.ASCENDING)])
        await db.zones.create_index([("name", pymongo.TEXT), ("description", pymongo.TEXT)])

        # Zone Audits collection indexes
        await db.zone_audits.create_index([("zone_id", pymongo.ASCENDING), ("changed_at", pymongo.DESCENDING)])
        await db.zone_audits.create_index("audit_id", unique=True, sparse=True)

        # Zone Transitions collection indexes (Prompt 10 Geofencing Engine)
        await db.zone_transitions.create_index("transition_id", unique=True, sparse=True)
        await db.zone_transitions.create_index("id", unique=True, sparse=True)
        await db.zone_transitions.create_index([("tourist_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.zone_transitions.create_index([("zone_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.zone_transitions.create_index([("event_type", pymongo.ASCENDING)])
        await db.zone_transitions.create_index([("timestamp", pymongo.DESCENDING)])
        await db.zone_transitions.create_index([("location", "2dsphere")], sparse=True)

        # Location History collection indexes
        # 1. Unique index on location_id and id
        await db.location_history.create_index("location_id", unique=True, sparse=True)
        await db.location_history.create_index("id", unique=True, sparse=True)
        # 2. Geospatial 2dsphere index on location field (GeoJSON Point)
        await db.location_history.create_index([("location", "2dsphere")])
        # 3. Compound and temporal indexes for high-throughput queries
        await db.location_history.create_index([("tourist_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.location_history.create_index([("session_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.location_history.create_index([("timestamp", pymongo.DESCENDING)])

        # Tracking Sessions collection indexes
        await db.tracking_sessions.create_index("session_id", unique=True, sparse=True)
        await db.tracking_sessions.create_index([("tourist_id", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)])
        await db.tracking_sessions.create_index([("status", pymongo.ASCENDING)])

        # Telemetry Collections indexes
        # 1. Telemetry Samples (Idempotency + High-throughput temporal queries)
        await db.telemetry_samples.create_index("packet_id", unique=True, sparse=True)
        await db.telemetry_samples.create_index([("session_id", pymongo.ASCENDING), ("sequence_number", pymongo.ASCENDING)], unique=True, sparse=True)
        await db.telemetry_samples.create_index([("tourist_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.telemetry_samples.create_index([("session_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.telemetry_samples.create_index([("timestamp", pymongo.DESCENDING)])
        await db.telemetry_samples.create_index([("location", "2dsphere")], sparse=True)

        # 2. Telemetry Windows (AI/ML foundation temporal indexes)
        await db.telemetry_windows.create_index("window_id", unique=True, sparse=True)
        await db.telemetry_windows.create_index([("session_id", pymongo.ASCENDING), ("window_start", pymongo.DESCENDING)])
        await db.telemetry_windows.create_index([("tourist_id", pymongo.ASCENDING), ("window_start", pymongo.DESCENDING)])
        await db.telemetry_windows.create_index([("window_start", pymongo.DESCENDING)])

        # 3. Telemetry Sessions
        await db.telemetry_sessions.create_index("session_id", unique=True, sparse=True)
        await db.telemetry_sessions.create_index([("tourist_id", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)])
        await db.telemetry_sessions.create_index([("status", pymongo.ASCENDING)])

        # 4. Export Jobs (Prompt 15 Analytics Foundation)
        await db.export_jobs.create_index("job_id", unique=True, sparse=True)
        await db.export_jobs.create_index([("requested_by", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
        await db.export_jobs.create_index([("status", pymongo.ASCENDING)])

        # 5. Identity & KYC Platform (Prompt 18)
        await db.tourist_identity_profiles.create_index("id", unique=True, sparse=True)
        await db.tourist_identity_profiles.create_index("user_id", unique=True, sparse=True)
        await db.tourist_identity_profiles.create_index([("identity_status", pymongo.ASCENDING)])

        await db.kyc_documents.create_index("id", unique=True, sparse=True)
        await db.kyc_documents.create_index([("tourist_id", pymongo.ASCENDING), ("submitted_at", pymongo.DESCENDING)])
        await db.kyc_documents.create_index([("identity_profile_id", pymongo.ASCENDING)])
        await db.kyc_documents.create_index([("verification_status", pymongo.ASCENDING)])
        await db.kyc_documents.create_index([("reviewer_id", pymongo.ASCENDING)], sparse=True)

        await db.kyc_verification_history.create_index("id", unique=True, sparse=True)
        await db.kyc_verification_history.create_index([("tourist_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.kyc_verification_history.create_index([("identity_profile_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])

        await db.digital_tourist_credentials.create_index("id", unique=True, sparse=True)
        await db.digital_tourist_credentials.create_index("credential_reference", unique=True, sparse=True)
        await db.digital_tourist_credentials.create_index([("user_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
        await db.digital_tourist_credentials.create_index([("expires_at", pymongo.ASCENDING)])

        await db.user_consents.create_index("id", unique=True, sparse=True)
        await db.user_consents.create_index([("user_id", pymongo.ASCENDING), ("consent_type", pymongo.ASCENDING)])

        await db.credential_verification_logs.create_index("id", unique=True, sparse=True)
        await db.credential_verification_logs.create_index([("credential_reference", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
        await db.credential_verification_logs.create_index([("verifier_user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)], sparse=True)

        # 6. Advanced Operational Analytics & Intelligence (Prompt 26)
        await db.incidents.create_index([("jurisdiction_id", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)], sparse=True)
        await db.incidents.create_index([("zone_id", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)], sparse=True)
        await db.incidents.create_index([("status", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)])
        await db.incidents.create_index([("escalation_level", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)])

        await db.safety_decisions.create_index([("jurisdiction_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)], sparse=True)
        await db.safety_decisions.create_index([("state", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])

        await db.anomaly_events.create_index([("jurisdiction_id", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)], sparse=True)
        await db.anomaly_events.create_index([("zone_id", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)], sparse=True)

        await db.risk_episodes.create_index("episode_id", unique=True, sparse=True)
        await db.risk_episodes.create_index([("jurisdiction_id", pymongo.ASCENDING), ("start_time", pymongo.DESCENDING)], sparse=True)
        await db.risk_episodes.create_index([("status", pymongo.ASCENDING), ("start_time", pymongo.DESCENDING)])

        await db.responder_assignments.create_index([("jurisdiction_id", pymongo.ASCENDING), ("assigned_at", pymongo.DESCENDING)], sparse=True)
        await db.responder_assignments.create_index([("responder_id", pymongo.ASCENDING), ("assigned_at", pymongo.DESCENDING)], sparse=True)
        await db.responder_assignments.create_index([("unit_id", pymongo.ASCENDING), ("assigned_at", pymongo.DESCENDING)], sparse=True)

        await db.analytics_alerts.create_index("alert_id", unique=True, sparse=True)
        await db.analytics_alerts.create_index([("jurisdiction_id", pymongo.ASCENDING), ("is_active", pymongo.ASCENDING), ("triggered_at", pymongo.DESCENDING)], sparse=True)

        await db.analytics_audit_logs.create_index("id", unique=True, sparse=True)
        await db.analytics_audit_logs.create_index([("jurisdiction_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)], sparse=True)
        await db.analytics_audit_logs.create_index([("action", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])

        print("✅ Geospatial and collection indexes successfully initialized.")
    except Exception as e:
        print(f"⚠️ Index initialization warning: {e}")