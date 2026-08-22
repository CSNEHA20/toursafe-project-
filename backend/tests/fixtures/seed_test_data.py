"""
TourSafe QA — Seed and Cleanup Helpers
Provides deterministic test data seeding and safe cleanup.
Only operates on toursafe_test database — refuses production database.
"""
import asyncio
import sys
import os


SAFE_DB_NAME = "toursafe_test"


def _assert_safe_database(db_name: str):
    if db_name == "toursafe":
        print("ERROR: Refusing to seed/clean production database 'toursafe'.")
        print("Set MONGODB_DATABASE=toursafe_test to run seeds against the test database.")
        sys.exit(1)
    if db_name != SAFE_DB_NAME:
        print(f"WARNING: Running against non-standard database '{db_name}'.")


async def seed_test_data():
    """Insert deterministic test data into toursafe_test."""
    db_name = os.getenv("MONGODB_DATABASE", SAFE_DB_NAME)
    _assert_safe_database(db_name)

    from motor.motor_asyncio import AsyncIOMotorClient
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    print(f"Seeding test data into: {db_name}")

    # Seed safe and danger zones
    await db["zones"].replace_one(
        {"id": "zone_safe_001"},
        {
            "id": "zone_safe_001",
            "zone_name": "QA Safe Beach Zone",
            "zone_type": "safe",
            "risk_level": "safe",
            "is_active": True,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [74.1200, 15.2950],
                    [74.1280, 15.2950],
                    [74.1280, 15.3030],
                    [74.1200, 15.3030],
                    [74.1200, 15.2950],
                ]]
            },
        },
        upsert=True,
    )

    await db["zones"].replace_one(
        {"id": "zone_danger_001"},
        {
            "id": "zone_danger_001",
            "zone_name": "QA Danger Ravine Zone",
            "zone_type": "danger",
            "risk_level": "danger",
            "is_active": True,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [74.1260, 15.3060],
                    [74.1360, 15.3060],
                    [74.1360, 15.3140],
                    [74.1260, 15.3140],
                    [74.1260, 15.3060],
                ]]
            },
        },
        upsert=True,
    )

    print("Test data seeded successfully.")
    client.close()


async def cleanup_test_data():
    """Remove all test-prefixed documents from toursafe_test."""
    db_name = os.getenv("MONGODB_DATABASE", SAFE_DB_NAME)
    _assert_safe_database(db_name)

    from motor.motor_asyncio import AsyncIOMotorClient
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    print(f"Cleaning test data from: {db_name}")

    collections = await db.list_collection_names()
    for cname in collections:
        coll = db[cname]
        # Remove documents with test-prefixed IDs
        result = await coll.delete_many({
            "$or": [
                {"id": {"$regex": "^(tourist_qa|user_tourist|responder_qa|user_responder|auth_op|user_auth|sos_qa|incident_qa|notif_qa|zone_qa|assignment_qa)"}},
                {"email": {"$regex": "@toursafe\\.test$"}},
            ]
        })
        if result.deleted_count > 0:
            print(f"  Cleaned {result.deleted_count} documents from '{cname}'")

    print("Test data cleanup complete.")
    client.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TourSafe QA Test Data Manager")
    parser.add_argument("action", choices=["seed", "cleanup"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "seed":
        asyncio.run(seed_test_data())
    elif args.action == "cleanup":
        asyncio.run(cleanup_test_data())
