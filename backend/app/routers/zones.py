from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..core.database import get_database
from ..models.zone import Zone, ZoneStatus, ZoneType, ZoneRiskLevel
from ..schemas.zone import ZoneTouristMapResponse, ZoneTouristMapItem

router = APIRouter(prefix="/api/v1/zones", tags=["zones"])


@router.get("", response_model=ZoneTouristMapResponse)
async def get_active_zones_for_map(
    zone_type: Optional[ZoneType] = Query(None, description="Filter by zone type: safe, warning, restricted"),
    risk_level: Optional[ZoneRiskLevel] = Query(None, description="Filter by risk level: low, medium, high, critical"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Max number of zones to return"),
):
    """
    Tourist & Map consumption endpoint:
    Returns active, published safety zones formatted with RFC 7946 GeoJSON geometry.
    Excludes internal administrative identifiers and draft/inactive zones.
    """
    db = get_database()
    filter_query = {
        "status": ZoneStatus.ACTIVE.value,
        "is_active": True,
    }

    if zone_type:
        filter_query["zone_type"] = zone_type.value if hasattr(zone_type, "value") else str(zone_type)
    if risk_level:
        filter_query["risk_level"] = risk_level.value if hasattr(risk_level, "value") else str(risk_level)

    cursor = db.zones.find(filter_query).skip(skip).limit(limit).sort("name", 1)
    zones_docs = await cursor.to_list(length=limit)
    total = await db.zones.count_documents(filter_query)

    items = []
    for doc in zones_docs:
        zone_id = doc.get("zone_id") or doc.get("id") or str(doc.get("_id", ""))
        items.append(
            ZoneTouristMapItem(
                zone_id=zone_id,
                name=doc.get("name", ""),
                description=doc.get("description", ""),
                type=doc.get("zone_type", "safe"),
                risk_level=doc.get("risk_level", "low"),
                status=doc.get("status", "active"),
                geometry=doc.get("boundary", {}),
                center=doc.get("center", {}),
                properties=doc.get("properties", {}),
            )
        )

    return ZoneTouristMapResponse(zones=items, total=total)


@router.get("/{zone_id}", response_model=ZoneTouristMapItem)
async def get_active_zone_by_id(
    zone_id: str,
):
    """
    Retrieve details of a specific active zone.
    """
    db = get_database()
    doc = await db.zones.find_one({
        "$or": [{"zone_id": zone_id}, {"id": zone_id}],
        "status": ZoneStatus.ACTIVE.value,
        "is_active": True,
    })

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active zone '{zone_id}' not found",
        )

    zid = doc.get("zone_id") or doc.get("id") or str(doc.get("_id", ""))
    return ZoneTouristMapItem(
        zone_id=zid,
        name=doc.get("name", ""),
        description=doc.get("description", ""),
        type=doc.get("zone_type", "safe"),
        risk_level=doc.get("risk_level", "low"),
        status=doc.get("status", "active"),
        geometry=doc.get("boundary", {}),
        center=doc.get("center", {}),
        properties=doc.get("properties", {}),
    )
