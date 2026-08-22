from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
import hmac
import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from ...models.identity import KYCDocumentType, KYCRejectionReason, KYCStatus, ProviderStatus

logger = logging.getLogger("toursafe.identity.provider")


class IdentityVerificationProvider(ABC):
    """
    Abstract interface for pluggable third-party KYC / Identity Verification Providers.
    Decoupled from specific vendor SDKs.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_real_provider(self) -> bool:
        """Whether this provider connects to a live legal KYC verification service."""
        pass

    @abstractmethod
    async def get_status(self) -> ProviderStatus:
        """Get provider availability status."""
        pass

    @abstractmethod
    async def submit_verification(
        self,
        tourist_id: str,
        document_type: KYCDocumentType,
        masked_identifier: str,
        storage_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit document metadata to verification provider."""
        pass

    @abstractmethod
    async def check_status(self, provider_reference: str) -> Dict[str, Any]:
        """Poll verification status from provider."""
        pass

    @abstractmethod
    async def cancel_verification(self, provider_reference: str) -> bool:
        """Cancel ongoing verification."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str, secret: str) -> bool:
        """Cryptographically verify provider webhook signature."""
        pass


class DevKYCProvider(IdentityVerificationProvider):
    """
    Development / Simulated KYC Provider.
    CRITICAL: Clearly labeled DEV_KYC_PROVIDER. It provides simulated workflow state
    for automated development and testing, and NEVER claims real-world government-backed identity verification.
    """

    def __init__(self, webhook_secret: str = "toursafe_dev_kyc_webhook_secret_key_32bytes"):
        self._provider_name = "DEV_KYC_PROVIDER"
        self._webhook_secret = webhook_secret
        self._processed_events: set = set()
        self._status = ProviderStatus.AVAILABLE

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def is_real_provider(self) -> bool:
        return False

    def set_mock_status(self, status: ProviderStatus):
        self._status = status

    async def get_status(self) -> ProviderStatus:
        return self._status

    async def submit_verification(
        self,
        tourist_id: str,
        document_type: KYCDocumentType,
        masked_identifier: str,
        storage_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._status == ProviderStatus.UNAVAILABLE:
            raise RuntimeError("DEV_KYC_PROVIDER is currently UNAVAILABLE")

        ref_id = f"DEV-KYC-{uuid.uuid4().hex[:10].upper()}"
        logger.info(
            "DEV_KYC_PROVIDER: Accepted simulated verification submission [tourist=%s, type=%s, ref=%s]",
            tourist_id,
            document_type,
            ref_id,
        )
        return {
            "provider": self.provider_name,
            "provider_reference": ref_id,
            "status": "PENDING",
            "message": "Development simulated verification queued. Real verification requires production provider.",
            "is_demo": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def check_status(self, provider_reference: str) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_reference": provider_reference,
            "status": "UNDER_REVIEW",
            "verified": False,
            "is_demo": True,
        }

    async def cancel_verification(self, provider_reference: str) -> bool:
        logger.info("DEV_KYC_PROVIDER: Cancelled verification %s", provider_reference)
        return True

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str, secret: Optional[str] = None) -> bool:
        sec = secret or self._webhook_secret
        expected = hmac.new(sec.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def record_processed_event(self, event_id: str) -> bool:
        """Idempotency check: returns True if event was new, False if duplicate."""
        if event_id in self._processed_events:
            return False
        self._processed_events.add(event_id)
        return True


class ProviderRegistry:
    """Registry of KYC Verification providers."""

    def __init__(self):
        self._providers: Dict[str, IdentityVerificationProvider] = {}
        self._default_provider_name: str = "DEV_KYC_PROVIDER"

        # Register default dev provider
        dev_provider = DevKYCProvider()
        self.register_provider(dev_provider, is_default=True)

    def register_provider(self, provider: IdentityVerificationProvider, is_default: bool = False):
        self._providers[provider.provider_name] = provider
        if is_default:
            self._default_provider_name = provider.provider_name
        logger.info("Registered identity provider: %s (real=%s, default=%s)", provider.provider_name, provider.is_real_provider, is_default)

    def get_provider(self, name: Optional[str] = None) -> IdentityVerificationProvider:
        provider_name = name or self._default_provider_name
        provider = self._providers.get(provider_name)
        if not provider:
            logger.warning("Provider %s not found. Falling back to default %s", provider_name, self._default_provider_name)
            return self._providers[self._default_provider_name]
        return provider

    def get_default_provider(self) -> IdentityVerificationProvider:
        return self.get_provider(self._default_provider_name)

    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "provider_name": name,
                "is_real_provider": p.is_real_provider,
                "is_default": name == self._default_provider_name,
            }
            for name, p in self._providers.items()
        }


# Global Provider Registry Singleton
provider_registry = ProviderRegistry()
