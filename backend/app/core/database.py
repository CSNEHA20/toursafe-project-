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

        print("✅ Geospatial and collection indexes successfully initialized.")
    except Exception as e:
        print(f"⚠️ Index initialization warning: {e}")