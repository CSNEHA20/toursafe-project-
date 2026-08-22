from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from ....schemas.integrations import (
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationStatus,
    IntegrationType,
)
from .base import IntegrationAdapter

logger = logging.getLogger("toursafe.integrations.adapters.government")


class GovernmentAuthorityAdapter(IntegrationAdapter):
    """
    Government & Public Safety Authority System Adapter.
    Provides read-only status telemetry queries and controlled emergency dispatch registration.
    """

    def __init__(
        self,
        provider_name: str = "DEV_GOVERNMENT_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.GOVERNMENT,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(
                provider_name=provider_name,
                integration_type=IntegrationType.GOVERNMENT,
                allowlist_domains=["gov.portal.local", "safety.gov.in"],
            ),
        )

    @property
    def capabilities(self) -> List[str]:
        return [
            "read_jurisdiction_policies",
            "read_public_advisories",
            "register_incident_report",
            "query_authority_resources",
        ]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 16.0
        status.is_healthy = True
        status.detail = f"Government Portal Gateway '{self.provider_name}' connected (Read/Write Ready)"
        return status

    async def query_public_advisories(self, region_code: str = "GOA_NORTH") -> List[Dict[str, Any]]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return [
            {
                "advisory_id": f"GOV-ADV-{region_code}-01",
                "authority": "Directorate of Tourism, Government of Goa",
                "title": "Monsoon Coastal Swimming Restrictions",
                "severity": "WARNING",
                "issued_at": datetime.now(timezone.utc).isoformat(),
                "content": "Red flags hoisted across all Calangute-Candolim beach stretches. Water sports strictly suspended.",
            }
        ]

    async def submit_government_incident_report(
        self,
        toursafe_incident_id: str,
        jurisdiction_id: str,
        incident_summary: str,
        actor_id: str,
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        gov_ref = f"GOV-INC-{uuid.uuid4().hex[:8].upper()}"
        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "status": "ACCEPTED",
            "government_reference_id": gov_ref,
            "toursafe_incident_id": toursafe_incident_id,
            "jurisdiction_id": jurisdiction_id,
            "submitted_by": actor_id,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
