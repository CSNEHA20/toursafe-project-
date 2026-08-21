from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.medical_profile import MedicalProfileCreate, MedicalProfileUpdate, MedicalProfileResponse
from ..models.medical_profile import MedicalProfile
from typing import List

router = APIRouter(prefix="/api/v1/tourists", tags=["tourists-medical"])


@router.get("/me/medical", response_model=MedicalProfileResponse)
async def get_medical_profile(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get medical profile for authenticated tourist."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Medical profile access required",
        )

    from ..app.services import get_medical_profile_service
    profile = await get_medical_profile_service(user_id)
    if not profile:
        # Return default empty profile
        return MedicalProfileResponse(
            id="",
            tourist_id=user_id,
            blood_group=None,
            allergies=[],
            medical_conditions=[],
            medications=[],
            disability_information=None,
            other_emergency_medical_notes=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    return MedicalProfileResponse(
        id=profile.id,
        tourist_id=profile.tourist_id,
        blood_group=profile.blood_group,
        allergies=profile.allergies,
        medical_conditions=profile.medical_conditions,
        medications=profile.medications,
        disability_information=profile.disability_information,
        other_emergency_medical_notes=profile.other_emergency_medical_notes,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.put("/me/medical", response_model=MedicalProfileResponse)
async def update_medical_profile(
    data: MedicalProfileUpdate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Update medical profile. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Medical profile update required",
        )

    from ..app.services import upsert_medical_profile_service
    profile = await upsert_medical_profile_service(user_id, data.model_dump(exclude_unset=True))

    return MedicalProfileResponse(
        id=profile.id,
        tourist_id=profile.tourist_id,
        blood_group=profile.blood_group,
        allergies=profile.allergies,
        medical_conditions=profile.medical_conditions,
        medications=profile.medications,
        disability_information=profile.disability_information,
        other_emergency_medical_notes=profile.other_emergency_medical_notes,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.delete("/me/medical", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medical_profile(
    user_id_role: tuple = Depends(get_current_user),
):
    """Delete medical profile. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Medical profile deletion required",
        )

    from ..app.services import delete_medical_profile_service
    await delete_medical_profile_service(user_id)