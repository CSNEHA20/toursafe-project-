"""
TourSafe - Seed Zones Initializer

Provides realistic initial geospatial safety zones for Tamil Nadu & Nilgiris.
All boundaries follow standard GeoJSON coordinate ordering: [longitude, latitude].
All mock/initial boundaries are explicitly marked with "dataset": "DEVELOPMENT GEOMETRY".
"""

from typing import Any, Dict, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..models.zone import Zone, ZoneType, ZoneRiskLevel, ZoneStatus, ZoneAudit, ZoneAuditAction


INITIAL_DEV_ZONES: List[Dict[str, Any]] = [
    {
        "id": "zone-kodaikanal-lake",
        "zone_id": "zone-kodaikanal-lake",
        "name": "Kodaikanal Lake & Boat Club Area",
        "description": "Safe perimeter covering Kodaikanal Lake, boat club, and pedestrian promenade. Police patrol active 08:00–18:00.",
        "zone_type": ZoneType.SAFE.value,
        "risk_level": ZoneRiskLevel.LOW.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4830, 10.2430],
                    [77.4950, 10.2430],
                    [77.4960, 10.2320],
                    [77.4840, 10.2310],
                    [77.4830, 10.2430],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [77.4892, 10.2381],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Kodaikanal, Dindigul District",
            "state": "Tamil Nadu",
            "alert_message": "You are in the Kodaikanal Lake safe zone. Police patrol active.",
            "emergency_contact": "112",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-guna-caves",
        "zone_id": "zone-guna-caves",
        "name": "Guna Caves (Devil's Kitchen)",
        "description": "High-risk restricted crevice sector. Steep vertical drop-offs and unstable rock formations. Entry strictly prohibited.",
        "zone_type": ZoneType.RESTRICTED.value,
        "risk_level": ZoneRiskLevel.CRITICAL.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4780, 10.2210],
                    [77.4880, 10.2210],
                    [77.4880, 10.2120],
                    [77.4780, 10.2120],
                    [77.4780, 10.2210],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [77.4833, 10.2167],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Kodaikanal, Dindigul District",
            "state": "Tamil Nadu",
            "alert_message": "DANGER: Guna Caves is restricted. Deep crevices, unstable terrain. Entry prohibited.",
            "emergency_contact": "112",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-coakers-walk",
        "zone_id": "zone-coakers-walk",
        "name": "Coaker's Walk Ridge Trail",
        "description": "High altitude ridge trail at 2133m elevation. Steep cliffs on the eastern slope. Dense mist common after 16:00.",
        "zone_type": ZoneType.WARNING.value,
        "risk_level": ZoneRiskLevel.MEDIUM.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4910, 10.2330],
                    [77.4990, 10.2330],
                    [77.4980, 10.2250],
                    [77.4900, 10.2250],
                    [77.4910, 10.2330],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [77.4947, 10.2291],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Kodaikanal, Dindigul District",
            "state": "Tamil Nadu",
            "alert_message": "Warning: High altitude ridge trail. Stay behind safety railings.",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-berijam-lake",
        "zone_id": "zone-berijam-lake",
        "name": "Berijam Lake Forest Reserve",
        "description": "Protected forest reserve and wildlife habitat. Strict permit required from the Forest Department. No entry after 15:00.",
        "zone_type": ZoneType.RESTRICTED.value,
        "risk_level": ZoneRiskLevel.HIGH.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4050, 10.1930],
                    [77.4280, 10.1930],
                    [77.4280, 10.1730],
                    [77.4050, 10.1730],
                    [77.4050, 10.1930],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [77.4167, 10.1833],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Kodaikanal Forest Division",
            "state": "Tamil Nadu",
            "alert_message": "RESTRICTED: Protected Forest Reserve. Permit required at Kodaikanal Forest Office.",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-pillar-rocks",
        "zone_id": "zone-pillar-rocks",
        "name": "Pillar Rocks Viewpoint",
        "description": "Warning zone near 400-foot vertical granite pillars. High wind speeds and sudden drop-offs beyond boundary fence.",
        "zone_type": ZoneType.WARNING.value,
        "risk_level": ZoneRiskLevel.MEDIUM.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4680, 10.2240],
                    [77.4780, 10.2240],
                    [77.4790, 10.2150],
                    [77.4690, 10.2150],
                    [77.4680, 10.2240],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [77.4736, 10.2194],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Kodaikanal, Dindigul District",
            "state": "Tamil Nadu",
            "alert_message": "Warning: 400-ft vertical rock pillars. Stay behind designated barricades.",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-ooty-botanical-gardens",
        "zone_id": "zone-ooty-botanical-gardens",
        "name": "Ooty Botanical Gardens",
        "description": "Safe, well-maintained Government Botanical Garden premises. 55-acre terraced garden with 24/7 security and first aid post.",
        "zone_type": ZoneType.SAFE.value,
        "risk_level": ZoneRiskLevel.LOW.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [76.6890, 11.4150],
                    [76.7010, 11.4150],
                    [76.7010, 11.4050],
                    [76.6890, 11.4050],
                    [76.6890, 11.4150],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [76.6950, 11.4102],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Ooty, Nilgiris District",
            "state": "Tamil Nadu",
            "alert_message": "Safe zone: Ooty Botanical Gardens. Open 07:00–18:30.",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-ooty-lake",
        "zone_id": "zone-ooty-lake",
        "name": "Ooty Lake & Boathouse",
        "description": "Safe family tourism recreation zone. Boating operations supervised by TTDC. Life jackets mandatory.",
        "zone_type": ZoneType.SAFE.value,
        "risk_level": ZoneRiskLevel.LOW.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [76.6960, 11.4050],
                    [76.7090, 11.4050],
                    [76.7090, 11.3950],
                    [76.6960, 11.3950],
                    [76.6960, 11.4050],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [76.7025, 11.4000],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Ooty, Nilgiris District",
            "state": "Tamil Nadu",
            "alert_message": "Safe zone: Ooty Lake. Boating supervised by TTDC.",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
    {
        "id": "zone-doddabetta-peak",
        "zone_id": "zone-doddabetta-peak",
        "name": "Doddabetta Peak Summit",
        "description": "Highest peak in the Nilgiri Hills at 2637m. Sudden dense fog, freezing winds, and rocky trails. Telescope house access.",
        "zone_type": ZoneType.WARNING.value,
        "risk_level": ZoneRiskLevel.HIGH.value,
        "status": ZoneStatus.ACTIVE.value,
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [76.7280, 11.4140],
                    [76.7420, 11.4140],
                    [76.7420, 11.4010],
                    [76.7280, 11.4010],
                    [76.7280, 11.4140],
                ]
            ],
        },
        "center": {
            "type": "Point",
            "coordinates": [76.7350, 11.4072],
        },
        "properties": {
            "dataset": "DEVELOPMENT GEOMETRY",
            "region": "Nilgiris District",
            "state": "Tamil Nadu",
            "alert_message": "Warning: Highest Nilgiris peak at 2637m. Reduced visibility in fog.",
        },
        "is_active": True,
        "created_by": "system_seed",
    },
]


async def seed_initial_zones(db: AsyncIOMotorDatabase) -> int:
    """
    Idempotently seeds initial development zones if they do not already exist in MongoDB.
    Returns the count of newly seeded zones.
    """
    seeded_count = 0
    now = datetime.now(timezone.utc)
    
    for zone_data in INITIAL_DEV_ZONES:
        zone_id = zone_data["id"]
        existing = await db.zones.find_one({"$or": [{"id": zone_id}, {"zone_id": zone_id}]})
        
        if not existing:
            doc = zone_data.copy()
            doc["created_at"] = now
            doc["updated_at"] = now
            await db.zones.insert_one(doc)
            
            # Create initial audit log for seed creation
            audit = ZoneAudit(
                zone_id=zone_id,
                action=ZoneAuditAction.CREATED,
                changed_by="system_seed",
                changed_at=now,
                new_values={"name": doc["name"], "zone_type": doc["zone_type"], "status": doc["status"]},
                change_summary="Initial system seed zone created",
            )
            await db.zone_audits.insert_one(audit.to_mongo_dict())
            seeded_count += 1

    return seeded_count
