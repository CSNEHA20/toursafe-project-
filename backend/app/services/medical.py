from datetime import datetime, timezone
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase


async def get_medical_profile_service(tourist_id: str, db: AsyncIOMotorDatabase = None):
    """Get or create medical profile for a tourist."""
    if db is None:
        from ..core.database import get_database
        db = get_database()

    collection = db["medical_profiles"]

    # Try to find existing profile
    profile = await collection.find_one({"tourist_id": tourist_id})
    if profile:
        return MedicalProfile.from_dict(profile)

    # Create new profile with default values
    profile = MedicalProfile(
        id="",
        tourist_id=tourist_id,
        blood_group=None,
        allergies=[],
        medical_conditions=[],
        medications=[],
        disability_information=None,
        other_emergency_medical_notes=None,
    )
    await collection.insert_one(profile.to_dict())
    return profile


async def upsert_medical_profile_service(tourist_id: str, data: dict, db: AsyncIOMotorDatabase = None):
    """Update or create medical profile."""
    if db is None:
        from ..core.database get_database
        db = get_database()

    collection = db["medical_profiles"]

    # Find existing profile
    profile = await collection.find_one({"tourist_id": tourist_id})

    if profile:
        # Update existing
        update_data = {k: v for k, v in data.items() if v is not None}
        if update_data:
            await collection.update_one(
                {"tourist_id": tourist_id},
                {"$set": {**update_data, "updated_at": datetime.now(timezone.utc)}}
            )
        updated = await collection.find_one({"tourist_id": tourist_id})
        return MedicalProfile.from_dict(updated)
    else:
        # Create new
        data["tourist_id"] = tourist_id
        data["id"] = str(uuid.uuid4()) if "id" in data else ""
        data["created_at"] = datetime.now(timezone.utc)
        data["updated_at"] = datetime.now(timezone.utc)
        await collection.insert_one(data)
        return MedicalProfile.from_dict(data)


async def delete_medical_profile_service(tourist_id: str, db: AsyncIOMotorDatabase = None):
    """Delete medical profile."""
    if db is None:
        from ..core.database get_database
        db = get_database()

    collection = db["medical_profiles"]
    await collection.delete_one({"tourist_id": tourist_id})