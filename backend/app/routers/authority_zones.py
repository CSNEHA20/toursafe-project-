from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import pymongo

from ..core.database import get_database
from ..routers.auth import require_role
from ..models.zone import (
    Zone,
    ZoneType,
    ZoneRiskLevel,
    ZoneStatus,
    ZoneAudit,
    ZoneAuditAction,
)
from ..schemas.zone import (
    ZoneCreateRequest,
    ZoneUpdateRequest,
    ZoneStatusTransitionRequest,
    ZoneResponse,
    ZoneListResponse,
    ZoneAuditResponse,
)
from ..core.geo_validation import (
    validate_zone_geometry,
    validate_point_geometry,
    compute_polygon_center,
    GeoValidationError,
)

router = APIRouter(prefix="/api/v1/authority/zones", tags=["authority-zones"])

# Valid status transitions map
VALID_STATUS_TRANSITIONS = {
    ZoneStatus.DRAFT.value: {ZoneStatus.ACTIVE.value, ZoneStatus.INACTIVE.value, ZoneStatus.DRAFT.value},
    ZoneStatus.ACTIVE.value: {ZoneStatus.INACTIVE.value, ZoneStatus.DRAFT.value, ZoneStatus.ACTIVE.value},
    ZoneStatus.INACTIVE.value: {ZoneStatus.ACTIVE.value, ZoneStatus.DRAFT.value, ZoneStatus.INACTIVE.value},
}


def doc_to_zone_response(doc: Dict[str, Any]) -> ZoneResponse:
    zone_id = doc.get("zone_id") or doc.get("id") or str(doc.get("_id", ""))
    return ZoneResponse(
        id=zone_id,
        zone_id=zone_id,
        name=doc.get("name", ""),
        description=doc.get("description", ""),
        zone_type=doc.get("zone_type", ZoneType.SAFE),
        risk_level=doc.get("risk_level", ZoneRiskLevel.LOW),
        status=doc.get("status", ZoneStatus.ACTIVE),
        boundary=doc.get("boundary", {}),
        center=doc.get("center", {}),
        properties=doc.get("properties", {}),
        is_active=doc.get("is_active", True),
        created_by=doc.get("created_by"),
        updated_by=doc.get("updated_by"),
        created_at=doc.get("created_at") or datetime.now(timezone.utc),
        updated_at=doc.get("updated_at") or datetime.now(timezone.utc),
    )


@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    payload: ZoneCreateRequest,
    current_user_id: str = Depends(require_role("authority", "admin")),
):
    """
    Create a new safety zone (Authority / Admin only).
    Validates RFC 7946 GeoJSON boundary and logs an immutable audit entry.
    """
    db = get_database()
    # Check for duplicate active zone with exact same name
    existing = await db.zones.find_one({
        "name": {"$regex": f"^{payload.name.strip()}$", "$options": "i"},
        "is_active": True,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active zone with name '{payload.name}' already exists",
        )

    # Validate geometry
    try:
        boundary_geom = validate_zone_geometry(payload.boundary, path="boundary")
        center_geom = payload.center or compute_polygon_center(boundary_geom)
        center_geom = validate_point_geometry(center_geom, path="center")
    except GeoValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid GeoJSON geometry: {str(e)}",
        )

    now = datetime.now(timezone.utc)
    new_zone = Zone(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else "",
        zone_type=payload.zone_type,
        risk_level=payload.risk_level,
        status=payload.status,
        boundary=boundary_geom,
        center=center_geom,
        properties=payload.properties or {},
        is_active=payload.is_active if payload.is_active is not None else True,
        created_by=current_user_id,
        updated_by=current_user_id,
        created_at=now,
        updated_at=now,
    )

    mongo_doc = new_zone.to_mongo_dict()
    await db.zones.insert_one(mongo_doc)

    # Record Audit Entry
    audit_entry = ZoneAudit(
        zone_id=new_zone.id,
        action=ZoneAuditAction.CREATED,
        changed_by=current_user_id,
        changed_at=now,
        new_values={
            "name": new_zone.name,
            "zone_type": new_zone.zone_type,
            "risk_level": new_zone.risk_level,
            "status": new_zone.status,
            "center": new_zone.center,
        },
        change_summary=f"Zone '{new_zone.name}' created by {current_user_id}",
    )
    await db.zone_audits.insert_one(audit_entry.to_mongo_dict())

    return doc_to_zone_response(mongo_doc)


@router.get("", response_model=ZoneListResponse)
async def list_authority_zones(
    q: Optional[str] = Query(None, description="Search term for name or description"),
    status_filter: Optional[ZoneStatus] = Query(None, alias="status", description="Filter by status"),
    zone_type: Optional[ZoneType] = Query(None, description="Filter by zone type"),
    risk_level: Optional[ZoneRiskLevel] = Query(None, description="Filter by risk level"),
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    sort_by: str = Query("created_at", description="Field to sort by: name, created_at, updated_at, risk_level"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    current_user_id: str = Depends(require_role("authority", "admin")),
):
    """
    List and filter all zones with pagination and search (Authority / Admin only).
    """
    db = get_database()
    query: Dict[str, Any] = {}

    if q:
        search_regex = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"name": search_regex}, {"description": search_regex}]

    if status_filter:
        query["status"] = status_filter.value if hasattr(status_filter, "value") else str(status_filter)

    if zone_type:
        query["zone_type"] = zone_type.value if hasattr(zone_type, "value") else str(zone_type)

    if risk_level:
        query["risk_level"] = risk_level.value if hasattr(risk_level, "value") else str(risk_level)

    # Sorting
    direction = pymongo.ASCENDING if sort_order.lower() == "asc" else pymongo.DESCENDING
    sort_field = sort_by if sort_by in ["name", "created_at", "updated_at", "risk_level", "status"] else "created_at"

    cursor = db.zones.find(query).sort(sort_field, direction).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    total = await db.zones.count_documents(query)

    items = [doc_to_zone_response(doc) for doc in docs]
    return ZoneListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_authority_zone_details(
    zone_id: str,
    current_user_id: str = Depends(require_role("authority", "admin")),
):
    """
    Get full zone details including administrative properties (Authority / Admin only).
    """
    db = get_database()
    doc = await db.zones.find_one({"$or": [{"zone_id": zone_id}, {"id": zone_id}]})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone_id}' not found",
        )
    return doc_to_zone_response(doc)


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str,
    payload: ZoneUpdateRequest,
    current_user_id: str = Depends(require_role("authority", "admin")),
):
    """
    Update safety zone fields, boundary, status, or risk level (Authority / Admin only).
    Validates status transitions and creates an audit record.
    """
    db = get_database()
    doc = await db.zones.find_one({"$or": [{"zone_id": zone_id}, {"id": zone_id}]})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone_id}' not found",
        )

    current_zone = Zone.from_mongo_dict(doc)
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        return doc_to_zone_response(doc)

    previous_values: Dict[str, Any] = {}
    new_values: Dict[str, Any] = {}
    audit_action = ZoneAuditAction.UPDATED

    # Check status transition
    if "status" in update_data and update_data["status"] is not None:
        target_status = update_data["status"]
        current_status = current_zone.status
        allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_status}' to '{target_status}'. Allowed: {list(allowed)}",
            )
        previous_values["status"] = current_status
        new_values["status"] = target_status
        audit_action = ZoneAuditAction.STATUS_CHANGED

    # Check geometry update
    if "boundary" in update_data and update_data["boundary"] is not None:
        try:
            valid_boundary = validate_zone_geometry(update_data["boundary"], path="boundary")
            update_data["boundary"] = valid_boundary
            # If center not explicitly passed, recompute
            if "center" not in update_data or update_data["center"] is None:
                update_data["center"] = compute_polygon_center(valid_boundary)
            else:
                update_data["center"] = validate_point_geometry(update_data["center"], path="center")

            previous_values["boundary"] = current_zone.boundary
            previous_values["center"] = current_zone.center
            new_values["boundary"] = update_data["boundary"]
            new_values["center"] = update_data["center"]
            audit_action = ZoneAuditAction.BOUNDARY_UPDATED
        except GeoValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid GeoJSON geometry: {str(e)}",
            )

    # Check risk level or type changes
    for field_name in ["name", "description", "zone_type", "risk_level", "properties", "is_active"]:
        if field_name in update_data and update_data[field_name] is not None:
            old_val = getattr(current_zone, field_name)
            new_val = update_data[field_name]
            if old_val != new_val:
                previous_values[field_name] = old_val
                new_values[field_name] = new_val

    now = datetime.now(timezone.utc)
    update_data["updated_at"] = now
    update_data["updated_by"] = current_user_id

    await db.zones.update_one(
        {"$or": [{"zone_id": zone_id}, {"id": zone_id}]},
        {"$set": update_data},
    )

    # Create Audit Record
    audit_entry = ZoneAudit(
        zone_id=current_zone.id,
        action=audit_action,
        changed_by=current_user_id,
        changed_at=now,
        previous_values=previous_values if previous_values else None,
        new_values=new_values if new_values else None,
        change_summary=f"Zone updated by {current_user_id}: {', '.join(new_values.keys())}",
    )
    await db.zone_audits.insert_one(audit_entry.to_mongo_dict())

    updated_doc = await db.zones.find_one({"$or": [{"zone_id": zone_id}, {"id": zone_id}]})
    return doc_to_zone_response(updated_doc)


@router.delete("/{zone_id}", response_model=Dict[str, Any])
async def delete_or_deactivate_zone(
    zone_id: str,
    hard_delete: bool = Query(False, description="If true, removes document completely. Default soft deactivates."),
    current_user_id: str = Depends(require_role("authority", "admin")),
):
    """
    Deactivate or delete a safety zone (Authority / Admin only).
    """
    db = get_database()
    doc = await db.zones.find_one({"$or": [{"zone_id": zone_id}, {"id": zone_id}]})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone_id}' not found",
        )

    now = datetime.now(timezone.utc)
    zid = doc.get("zone_id") or doc.get("id")

    if hard_delete:
        await db.zones.delete_one({"$or": [{"zone_id": zone_id}, {"id": zone_id}]})
    else:
        await db.zones.update_one(
            {"$or": [{"zone_id": zone_id}, {"id": zone_id}]},
            {
                "$set": {
                    "is_active": False,
                    "status": ZoneStatus.INACTIVE.value,
                    "updated_at": now,
                    "updated_by": current_user_id,
                }
            },
        )

    # Log audit entry
    audit_entry = ZoneAudit(
        zone_id=zid,
        action=ZoneAuditAction.DELETED,
        changed_by=current_user_id,
        changed_at=now,
        previous_values={"name": doc.get("name"), "status": doc.get("status")},
        new_values={"is_active": False, "status": ZoneStatus.INACTIVE.value, "hard_delete": hard_delete},
        change_summary=f"Zone '{doc.get('name')}' {'deleted' if hard_delete else 'deactivated'} by {current_user_id}",
    )
    await db.zone_audits.insert_one(audit_entry.to_mongo_dict())

    return {
        "success": True,
        "zone_id": zid,
        "message": f"Zone '{doc.get('name')}' {'permanently deleted' if hard_delete else 'deactivated'}",
    }


@router.get("/{zone_id}/audits", response_model=List[ZoneAuditResponse])
async def get_zone_audit_history(
    zone_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user_id: str = Depends(require_role("authority", "admin")),
):
    """
    Get audit history and change log for a specific safety zone (Authority / Admin only).
    """
    db = get_database()
    cursor = db.zone_audits.find({"zone_id": zone_id}).sort("changed_at", pymongo.DESCENDING).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    results = []
    for doc in docs:
        results.append(
            ZoneAuditResponse(
                id=doc.get("id") or doc.get("audit_id") or str(doc.get("_id", "")),
                audit_id=doc.get("audit_id") or doc.get("id") or str(doc.get("_id", "")),
                zone_id=doc.get("zone_id", zone_id),
                action=doc.get("action", ZoneAuditAction.UPDATED),
                changed_by=doc.get("changed_by", ""),
                changed_at=doc.get("changed_at") or datetime.now(timezone.utc),
                previous_values=doc.get("previous_values"),
                new_values=doc.get("new_values"),
                change_summary=doc.get("change_summary"),
            )
        )
    return results
