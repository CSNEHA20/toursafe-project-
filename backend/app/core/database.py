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

        print("✅ Geospatial and collection indexes successfully initialized.")
    except Exception as e:
        print(f"⚠️ Index initialization warning: {e}")