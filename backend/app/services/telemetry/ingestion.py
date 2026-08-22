import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from ...core.config import settings
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...schemas.telemetry import (
    QualityMetrics,
    QualityStateEnum,
    SessionStatusEnum,
    TelemetryAck,
    TelemetryAckStatus,
    TelemetryBatchAck,
    TelemetryPacketEnvelope,
    TelemetrySample,
    TelemetryWindow,
)
from ..realtime_bus import realtime_bus
from .persistence import telemetry_persistence
from .quality import quality_evaluator
from .queue import telemetry_queue
from .redis_state import telemetry_redis_state
from .session import telemetry_session_manager
from .validation import TelemetryValidationException, telemetry_validator
from .windowing import telemetry_window_engine
from ..ml.engine import ml_inference_engine
from ..safety import safety_orchestrator, SafetySignalFactory

logger = logging.getLogger("toursafe.telemetry.ingestion")


class TelemetryIngestionService:
    """
    Main Telemetry Ingestion Service.
    Orchestrates validation, sequence management, idempotency, live state updates,
    durable storage, window extraction, and operational realtime events.
    """

    def __init__(self):
        self.total_ingested_today: int = 0
        # Wire queue processor
        telemetry_queue.set_processor(self._async_persistence_worker)

    async def _async_persistence_worker(self, item: Any):
        """Asynchronously persists sample and any generated windows to MongoDB."""
        if isinstance(item, TelemetrySample):
            await telemetry_persistence.persist_sample(item)
        elif isinstance(item, TelemetryWindow):
            await telemetry_persistence.persist_window(item)

    async def ingest_packet(
        self,
        envelope: TelemetryPacketEnvelope,
        authenticated_tourist_id: str,
        user_id: str,
    ) -> TelemetryAck:
        """
        Executes the 15-step ingestion pipeline on a single incoming telemetry packet.
        """
        now_dt = datetime.now(timezone.utc)
        server_received_at = now_dt.isoformat()

        # Step 1: Session lookup / validation
        session_state = await telemetry_session_manager.get_or_create_session(
            session_id=envelope.session_id,
            tourist_id=authenticated_tourist_id,
            user_id=user_id,
            device_id=envelope.device_id,
        )

        if session_state.status == SessionStatusEnum.STOPPED:
            session_state.invalid_packets += 1
            return TelemetryAck(
                status=TelemetryAckStatus.REJECTED,
                packet_id=envelope.packet_id,
                session_id=envelope.session_id,
                sequence_number=envelope.sequence_number,
                highest_contiguous_sequence=session_state.highest_contiguous_sequence,
                server_received_at=server_received_at,
                detail="Telemetry session is stopped",
            )

        # Step 2: Timestamp & Envelope Normalization
        try:
            sample_dt, transport_latency_ms = telemetry_validator.validate_timestamp(envelope.timestamp)
            sample = telemetry_validator.normalize_envelope(
                envelope=envelope,
                authenticated_tourist_id=authenticated_tourist_id,
                user_id=user_id,
            )
        except TelemetryValidationException as ve:
            session_state.invalid_packets += 1
            return TelemetryAck(
                status=TelemetryAckStatus.INVALID,
                packet_id=envelope.packet_id,
                session_id=envelope.session_id,
                sequence_number=envelope.sequence_number,
                highest_contiguous_sequence=session_state.highest_contiguous_sequence,
                server_received_at=server_received_at,
                detail=ve.message,
            )

        # Step 3: Sequence Management & Idempotency Evaluation
        seq_status = session_state.process_sequence(
            packet_id=sample.packet_id,
            seq=sample.sequence_number,
            sample_dt=sample_dt,
        )

        if seq_status == TelemetryAckStatus.DUPLICATE:
            return TelemetryAck(
                status=TelemetryAckStatus.DUPLICATE,
                packet_id=sample.packet_id,
                session_id=sample.session_id,
                sequence_number=sample.sequence_number,
                highest_contiguous_sequence=session_state.highest_contiguous_sequence,
                server_received_at=server_received_at,
                detail="Duplicate packet ignored (idempotent)",
            )

        # Update session timestamp tracking
        session_state.last_packet_timestamp = sample.timestamp
        if sample.gps:
            session_state.last_gps_timestamp = sample.timestamp
        if sample.accelerometer:
            session_state.last_imu_timestamp = sample.timestamp

        # Step 4: Empirical Quality Calculation
        observed_hz = None
        if session_state.last_gap_duration_ms > 0:
            observed_hz = round(1000.0 / max(1.0, session_state.last_gap_duration_ms), 2)

        out_of_order_ratio = (
            session_state.out_of_order_packets / max(1, session_state.total_packets)
        )

        quality = quality_evaluator.compute_metrics(
            gps_accuracy=sample.gps.accuracy if sample.gps else None,
            observed_imu_hz=observed_hz,
            target_hz=settings.telemetry_nominal_frequency_hz,
            sync_delta_ms=0.0,
            transport_latency_ms=transport_latency_ms,
            last_gap_duration_ms=session_state.last_gap_duration_ms,
            out_of_order_ratio=out_of_order_ratio,
        )
        sample.quality = quality

        # Step 5: Update Redis Live State
        await telemetry_redis_state.update_live_state(
            sample=sample,
            quality=quality,
            session_status=session_state.status,
        )

        # Step 6: Enqueue for Durable Persistence (Bounded Backpressure Queue)
        enqueued = telemetry_queue.enqueue(sample)
        if not enqueued:
            # Fallback direct async persistence if queue full
            asyncio.create_task(telemetry_persistence.persist_sample(sample))

        self.total_ingested_today += 1

        # Step 7: Temporal Window Engine
        windows = await telemetry_window_engine.ingest_and_evaluate_windows(sample)
        for w in windows:
            session_state.window_count += 1
            if w.is_valid:
                session_state.valid_window_count += 1
            else:
                session_state.invalid_window_count += 1
            # Persist generated window
            telemetry_queue.enqueue(w)
            # Submit to Real-Time ML Inference Engine
            ml_inference_engine.submit_window(w)

        # Step 8: Publish Summarized Realtime Events (Periodic or on change)
        # Note: Raw 50Hz IMU is strictly NOT broadcast to authorities!
        if sample.sequence_number % 50 == 0 or sample.gps is not None:
            await self._broadcast_operational_telemetry_status(
                tourist_id=authenticated_tourist_id,
                session_state=session_state,
                quality=quality,
            )

        # Step 9: Return Acknowledgement
        return TelemetryAck(
            status=seq_status,
            packet_id=sample.packet_id,
            session_id=sample.session_id,
            sequence_number=sample.sequence_number,
            highest_contiguous_sequence=session_state.highest_contiguous_sequence,
            server_received_at=server_received_at,
        )

    async def ingest_packet_batch(
        self,
        session_id: str,
        packets: List[TelemetryPacketEnvelope],
        authenticated_tourist_id: str,
        user_id: str,
    ) -> TelemetryBatchAck:
        """
        Processes a bounded batch of telemetry packets efficiently (e.g., from offline replay).
        """
        accepted = 0
        duplicates = 0
        out_of_order = 0
        rejected = 0

        last_ack: Optional[TelemetryAck] = None
        for pkt in packets:
            # Enforce session_id from batch header
            pkt.session_id = session_id
            ack = await self.ingest_packet(
                envelope=pkt,
                authenticated_tourist_id=authenticated_tourist_id,
                user_id=user_id,
            )
            last_ack = ack
            if ack.status == TelemetryAckStatus.ACCEPTED:
                accepted += 1
            elif ack.status == TelemetryAckStatus.DUPLICATE:
                duplicates += 1
            elif ack.status == TelemetryAckStatus.OUT_OF_ORDER:
                out_of_order += 1
            else:
                rejected += 1

        highest_contig = last_ack.highest_contiguous_sequence if last_ack else 0

        return TelemetryBatchAck(
            status="batch_processed",
            session_id=session_id,
            accepted_count=accepted,
            duplicate_count=duplicates,
            out_of_order_count=out_of_order,
            rejected_count=rejected,
            highest_contiguous_sequence=highest_contig,
            server_received_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _broadcast_operational_telemetry_status(
        self,
        tourist_id: str,
        session_state: Any,
        quality: QualityMetrics,
    ):
        """
        Broadcasts lightweight summarized operational telemetry status.
        Does NOT leak raw 50 Hz IMU sensor samples.
        """
        envelope = RealtimeEventEnvelope(
            event_type="telemetry.status.updated",
            source="telemetry_pipeline",
            payload={
                "tourist_id": tourist_id,
                "session_id": session_state.session_id,
                "tracking_status": session_state.status.value,
                "highest_sequence": session_state.highest_sequence,
                "highest_contiguous_sequence": session_state.highest_contiguous_sequence,
                "overall_quality": quality.overall_quality.value,
                "gps_quality": quality.gps_quality.value,
                "imu_quality": quality.imu_quality.value,
                "last_packet_timestamp": session_state.last_packet_timestamp,
                "window_count": session_state.window_count,
            },
        )
        try:
            # Broadcast to tourist channel and authority operations channel
            await realtime_bus.publish_to_channel(f"tourist:{tourist_id}", envelope)
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as pe:
            logger.debug("Operational telemetry event broadcast note: %s", pe)

        # Ingest Telemetry quality signal to Safety Orchestration Engine (Prompt 11)
        try:
            tel_sig = SafetySignalFactory.create_telemetry_signal(
                tourist_id=tourist_id,
                session_id=session_state.session_id,
                overall_quality=quality.overall_quality.value,
                observed_frequency_hz=quality.observed_imu_frequency_hz or 50.0,
                completeness_ratio=1.0 - (quality.out_of_order_ratio or 0.0),
                network_status="online",
                timestamp=session_state.last_packet_timestamp,
            )
            asyncio.create_task(safety_orchestrator.ingest_signal(tel_sig))
        except Exception as se_err:
            logger.debug("Safety engine telemetry ingest note: %s", se_err)


telemetry_service = TelemetryIngestionService()
