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

logger = logging.getLogger("toursafe.integrations.adapters.document")


class DocumentAdapter(IntegrationAdapter):
    """
    Document Storage & Vault Adapter (AWS S3, GCP Cloud Storage, MinIO, Encrypted Digilocker).
    """

    def __init__(
        self,
        provider_name: str = "DEV_DOCUMENT_VAULT",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.DOCUMENT,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.DOCUMENT),
        )
        self._vault_store: Dict[str, Dict[str, Any]] = {}

    @property
    def capabilities(self) -> List[str]:
        return ["upload_encrypted_document", "generate_presigned_url", "delete_document", "verify_checksum"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 5.0
        status.is_healthy = True
        status.detail = f"Document Vault '{self.provider_name}' operational"
        return status

    async def upload_document(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        encryption_key_id: Optional[str] = "kms-key-default",
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        doc_key = f"docs/vault/{uuid.uuid4().hex[:12]}_{file_name}"
        self._vault_store[doc_key] = {
            "size_bytes": len(file_bytes),
            "mime_type": mime_type,
            "encryption_key_id": encryption_key_id,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "storage_key": doc_key,
            "file_name": file_name,
            "size_bytes": len(file_bytes),
            "encrypted": True,
            "provider": self.provider_name,
        }
