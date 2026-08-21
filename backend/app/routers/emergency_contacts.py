from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.emergency_contact import (
    EmergencyContactCreate,
    EmergencyContactUpdate,
    EmergencyContactResponse,
    EmergencyContactList,
)
from ..models.emergency_contact import EmergencyContact
from typing import List


router = APIRouter(prefix="/api/v1/tourists", tags=["tourists-emergency-contacts"])


def get_tourist_db(db = Depends(get_database)):
    return db["tourists"]


def get_emergency_contacts_db(db = Depends(get_database)):
    return db["emergency_contacts"]


@router.get("/me/emergency-contacts", response_model=EmergencyContactList)
async def list_emergency_contacts(
    user_id_role: tuple = Depends(get_current_user),
):
    """List emergency contacts for authenticated tourist."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Emergency contacts access required",
        )

    contacts_db = get_emergency_contacts_db()
    contacts = await contacts_db.find({"tourist_id": user_id}).to_list(length=None)
    
    items = []
    for c in contacts:
        items.append(EmergencyContactResponse(
            id=c["id"],
            tourist_id=c["tourist_id"],
            name=c["name"],
            relationship=c["relationship"],
            phone=c["phone"],
            alternate_phone=c.get("alternate_phone"),
            email=c.get("email"),
            priority=c.get("priority", 1),
            is_primary=c.get("is_primary", False),
            created_at=c.get("created_at"),
            updated_at=c.get("updated_at"),
        ))

    return EmergencyContactList(
        items=items,
        total=len(items),
        page=1,
        per_page=len(items),
    )


@router.post("/me/emergency-contacts", response_model=EmergencyContactResponse, status_code=status.HTTP_201_CREATED)
async def create_emergency_contact(
    data: EmergencyContactCreate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Create a new emergency contact. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Emergency contacts access required",
        )

    # Validate priority uniqueness - prevent duplicate priorities
    contacts_db = get_emergency_contacts_db()
    existing = await contacts_db.find_one({"tourist_id": user_id, "priority": data.priority})
    if existing:
        # Demote existing contact
        await contacts_db.update_one(
            {"tourist_id": user_id, "priority": data.priority},
            {"$set": {"priority": existing.priority + 1, "is_primary": False}},
        )

    contact = EmergencyContact(
        id="",
        tourist_id=user_id,
        name=data.name,
        relationship=data.relationship,
        phone=data.phone,
        alternate_phone=data.alternate_phone,
        email=data.email,
        priority=data.priority,
    )
    await contacts_db.insert_one(contact.to_dict())

    return EmergencyContactResponse(
        id=contact.id,
        tourist_id=contact.tourist_id,
        name=contact.name,
        relationship=contact.relationship,
        phone=contact.phone,
        alternate_phone=contact.alternate_phone,
        email=contact.email,
        priority=contact.priority,
        is_primary=contact.is_primary,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.patch("/me/emergency-contacts/{contact_id}", response_model=EmergencyContactResponse)
async def update_emergency_contact(
    contact_id: str,
    data: EmergencyContactUpdate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Update an emergency contact. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Emergency contacts access required",
        )

    contacts_db = get_emergency_contacts_db()

    # Verify ownership - contact must belong to this tourist
    contact = await contacts_db.find_one({
        "tourist_id": user_id,
        "id": contact_id,
    })
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency contact not found or access denied",
        )

    # Validate priority uniqueness if being changed
    if data.priority is not None and data.priority != contact.get("priority"):
        existing = await contacts_db.find_one({
            "tourist_id": user_id,
            "priority": data.priority,
            "id": {"$ne": contact_id},
        })
        if existing:
            await contacts_db.update_one(
                {"tourist_id": user_id, "priority": data.priority},
                {"$set": {"priority": existing.priority + 1, "is_primary": False}},
            )

    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    await contacts_db.update_one(
        {"tourist_id": user_id, "id": contact_id},
        {"$set": update_data},
    )

    updated = await contacts_db.find_one({"tourist_id": user_id, "id": contact_id})
    return EmergencyContactResponse(
        id=updated["id"],
        tourist_id=updated["tourist_id"],
        name=updated["name"],
        relationship=updated["relationship"],
        phone=updated["phone"],
        alternate_phone=updated.get("alternate_phone"),
        email=updated.get("email"),
        priority=updated.get("priority", 1),
        is_primary=updated.get("is_primary", False),
        created_at=updated.get("created_at"),
        updated_at=updated.get("updated_at"),
    )


@router.delete("/me/emergency-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emergency_contact(
    contact_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Delete an emergency contact. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Emergency contacts access required",
        )

    contacts_db = get_emergency_contacts_db()

    # Verify ownership - contact must belong to this tourist
    result = await contacts_db.delete_one({
        "tourist_id": user_id,
        "id": contact_id,
    })
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency contact not found or access denied",
        )