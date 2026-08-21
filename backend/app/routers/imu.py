import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.imu import (
    IMUBatchAck,
    IMUSampleBatchIn,
    IMUSampleIn,
    IMUSessionResponse,
    IMUSessionStartRequest,
    IMUTelemetryAck,
)

logger = logging.getLogger("toursafe.imu.router")

router = APIRouter(tags=["IMU Telemetry"])


async def resolve_tourist_id(user_id: str, role: str) -> str:
    """Helper to resolve the tourist_id corresponding to authenticated user."""
    db = get_database()
    tourist_doc = await db["tourists"].find_one({"user_id": user_id})
    if tourist_doc:
        return tourist_doc.get("id", user_id)
    return user_id


# ─── 1. Ingest Single IMU Sample ──────────────────────────────────────────────

@router.post(
    "/api/v1/telemetry/imu",
    response_model=IMUTelemetryAck,
    status_code=status.HTTP_200_OK,
    summary="Ingest Realtime IMU Telemetry Sample",
)
async def ingest_imu_sample(
    sample: IMUSampleIn,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authenticated endpoint to ingest a physical device IMU sample.
    Validates channels, timestamps, and sequence numbers.
    Recomputes magnitudes on server for validation.
    Returns lightweight acknowledgement.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can transmit IMU telemetry",
        )

    tourist_id = await resolve_tourist_id(user_id, role)

    # Recompute server-side kinematics magnitudes
    derived = sample.calculate_server_magnitudes()

    return IMUTelemetryAck(
        status="accepted",
        session_id=sample.session_id,
        sequence_number=sample.sequence_number,
        recomputed_acceleration_magnitude=derived.acceleration_magnitude,
        recomputed_angular_velocity_magnitude=derived.angular_velocity_magnitude,
    )


# ─── 2. Ingest High-Frequency IMU Batch ───────────────────────────────────────

@router.post(
    "/api/v1/telemetry/imu/batch",
    response_model=IMUBatchAck,
    status_code=status.HTTP_200_OK,
    summary="Ingest Bounded Batch of IMU Telemetry Samples",
)
async def ingest_imu_batch(
    batch: IMUSampleBatchIn,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authenticated endpoint to ingest a bounded batch of 50 Hz IMU telemetry samples.
    Validates batch integrity and sequence ordering.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can transmit IMU telemetry",
        )

    if not batch.samples:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch contains no samples",
        )

    last_seq = batch.samples[-1].sequence_number

    return IMUBatchAck(
        status="accepted",
        session_id=batch.session_id,
        accepted_count=len(batch.samples),
        last_sequence_number=last_seq,
    )
