from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from ....schemas.integrations import (
    ExternalEmergencyRequest,
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationStatus,
    IntegrationType,
)
from ..conflict_resolver import conflict_service
from ..security import security_manager
from .base import IntegrationAdapter

logger = logging.getLogger("toursafe.integrations.adapters.emergency")


class EmergencyServiceAdapter(IntegrationAdapter):
    """
    Emergency Service / CAD (Computer-Aided Dispatch) Adapter Interface.
    Normalizes outbound incident dispatches and external reference sync across 112/911/CAD agency APIs.
    """

    def __init__(
        self,
        provider_name: str = "DEV_EMERGENCY_CAD_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.EMERGENCY_SERVICE,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(
                provider_name=provider_name,
                integration_type=IntegrationType.EMERGENCY_SERVICE,
                allowlist_domains=["cad.emergency.local", "dispatch.112.gov.in"],
            ),
        )
        self._external_requests: Dict[str, Dict[str, Any]] = {}

    @property
    def capabilities(self) -> List[str]:
        return [
            "create_emergency_request",
            "update_emergency_request",
            "cancel_emergency_request",
            "get_external_status",
            "bidirectional_sync",
        ]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 9.0
        status.is_healthy = True
        status.detail = f"Emergency Dispatch CAD interface '{self.provider_name}' operational"
        return status

    async def create_emergency_request(
        self,
        toursafe_incident_id: str,
        severity: str,
        incident_type: str,
        latitude: float,
        longitude: float,
        location_description: str,
        description: str,
        contact_name: str,
        contact_phone: Optional[str] = None,
        responder_units_requested: int = 1,
    ) -> ExternalEmergencyRequest:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        ext_incident_id = f"CAD-{uuid.uuid4().hex[:8].upper()}"

        # Emergency data mapping with safety minimization
        masked_contact = contact_name
        if len(contact_name.split()) > 1:
            parts = contact_name.split()
            masked_contact = f"{parts[0]} {parts[1][0]}."

        req = ExternalEmergencyRequest(
            external_system=self.provider_name,
            external_incident_id=ext_incident_id,
            toursafe_incident_id=toursafe_incident_id,
            severity=severity,
            incident_type=incident_type,
            fuzzed_latitude=round(latitude, 5),
            fuzzed_longitude=round(longitude, 5),
            location_description=location_description,
            description=description,
            responder_units_requested=responder_units_requested,
            contact_name_masked=masked_contact,
            status="DISPATCHED",
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

        self._external_requests[ext_incident_id] = req.dict()

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        logger.info(
            "EmergencyAdapter (%s): Created external request %s for TourSafe incident %s",
            self.provider_name,
            ext_incident_id,
            toursafe_incident_id,
        )
        return req

    async def update_external_status(
        self,
        external_incident_id: str,
        new_external_status: str,
        toursafe_current_status: str,
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        req_data = self._external_requests.get(external_incident_id)
        if not req_data:
            raise KeyError(f"External incident {external_incident_id} not found in {self.provider_name}")

        req_data["status"] = new_external_status
        req_data["synced_at"] = datetime.now(timezone.utc).isoformat()
        toursafe_incident_id = req_data.get("toursafe_incident_id", "")

        # Check for state conflict
        conflict = await conflict_service.detect_or_record_conflict(
            toursafe_incident_id=toursafe_incident_id,
            external_system=self.provider_name,
            external_incident_id=external_incident_id,
            toursafe_status=toursafe_current_status,
            external_status=new_external_status,
        )

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "external_incident_id": external_incident_id,
            "toursafe_incident_id": toursafe_incident_id,
            "external_status": new_external_status,
            "has_conflict": conflict is not None,
            "conflict_id": conflict.conflict_id if conflict else None,
        }
