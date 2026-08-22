from datetime import datetime, timezone
import hashlib
import hmac
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

logger = logging.getLogger("toursafe.integrations.adapters.identity")


class IdentityProviderAdapter(IntegrationAdapter):
    """
    Identity & KYC Provider Adapter.
    Decoupled from specific vendor SDKs (e.g. Persona, Trulioo, Onfido, Digilocker).
    """

    def __init__(
        self,
        provider_name: str = "DEV_IDENTITY_PROVIDER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.IDENTITY,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.IDENTITY),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["kyc_verification", "document_ocr", "biometric_liveness", "credential_issuance", "webhook_callback"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 14.0
        status.is_healthy = True
        status.detail = f"Identity Provider '{self.provider_name}' operational"
        return status

    async def submit_verification(
        self,
        tourist_id: str,
        document_type: str,
        masked_identifier: str,
        document_storage_key: Optional[str] = None,
        consent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        ref_id = f"KYC-EXT-{uuid.uuid4().hex[:10].upper()}"
        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "status": "PENDING",
            "provider": self.provider_name,
            "provider_reference": ref_id,
            "tourist_id": tourist_id,
            "document_type": document_type,
            "is_real_provider": self.is_real_provider,
            "message": "Identity verification submission queued.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def check_status(self, provider_reference: str) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        # In dev mode, return VERIFIED
        return {
            "provider": self.provider_name,
            "provider_reference": provider_reference,
            "status": "VERIFIED",
            "verified": True,
            "is_real_provider": self.is_real_provider,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str, secret: str) -> bool:
        if not signature_header or not secret:
            return False
        clean_sig = signature_header.split("=")[-1].strip()
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(clean_sig, expected)
