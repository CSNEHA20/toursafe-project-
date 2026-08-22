from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple
import uuid

from ...schemas.integrations import InboundWebhookResult, IntegrationType
from .dead_letter import dead_letter_service
from .idempotency import idempotency_manager
from .security import security_manager

logger = logging.getLogger("toursafe.integrations.webhooks")

MAX_WEBHOOK_AGE_SECONDS = 300  # 5 minutes replay prevention window


class WebhookVerificationException(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Webhook Verification Failed: {reason}")
        self.reason = reason


class WebhookManager:
    """
    Inbound Webhook Security and Dispatch Engine.
    Handles cryptographic verification, timestamp window validation, anti-replay nonces,
    payload normalization, and idempotency guarantees.
    """

    def __init__(self):
        self._processed_events: Dict[str, float] = {}  # event_id -> timestamp
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]] = {}

    def register_handler(
        self,
        provider_name: str,
        handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]],
    ) -> None:
        self._handlers[provider_name.lower()] = handler
        logger.info("WebhookManager: Registered webhook handler for '%s'", provider_name)

    @staticmethod
    def verify_hmac_signature(
        raw_body: bytes,
        signature_header: str,
        secret: str,
        algorithm: str = "sha256",
    ) -> bool:
        """Verifies HMAC signature against payload bytes."""
        if not signature_header or not secret:
            return False

        # Support 'sha256=...' or raw hex
        clean_sig = signature_header.split("=")[-1].strip()
        hash_func = getattr(hashlib, algorithm, hashlib.sha256)
        expected = hmac.new(secret.encode("utf-8"), raw_body, hash_func).hexdigest()
        return hmac.compare_digest(clean_sig, expected)

    async def process_inbound_webhook(
        self,
        provider_type: str,
        provider_name: str,
        raw_body: bytes,
        headers: Dict[str, str],
        secret: Optional[str] = None,
    ) -> InboundWebhookResult:
        correlation_id = f"wh_corr_{uuid.uuid4().hex[:10]}"
        provider_key = provider_name.lower()
        now_ts = datetime.now(timezone.utc).timestamp()

        # 1. Parse JSON payload
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as e:
            logger.error("WebhookManager: Invalid JSON from %s: %s", provider_name, e)
            raise WebhookVerificationException("Invalid JSON payload structure")

        # 2. Extract Event ID & Timestamp
        event_id = (
            payload.get("event_id")
            or payload.get("id")
            or headers.get("x-webhook-id")
            or headers.get("x-event-id")
            or f"evt_{uuid.uuid4().hex[:12]}"
        )
        timestamp_header = (
            headers.get("x-webhook-timestamp")
            or headers.get("x-timestamp")
            or payload.get("timestamp")
        )

        # 3. Check Timestamp Window (Anti-Replay)
        if timestamp_header:
            try:
                if isinstance(timestamp_header, (int, float)):
                    event_ts = float(timestamp_header)
                else:
                    event_ts = datetime.fromisoformat(str(timestamp_header).replace("Z", "+00:00")).timestamp()

                age = abs(now_ts - event_ts)
                if age > MAX_WEBHOOK_AGE_SECONDS:
                    logger.warning("WebhookManager: Webhook from %s rejected due to stale timestamp (age=%.1fs)", provider_name, age)
                    raise WebhookVerificationException(f"Webhook timestamp is outside acceptable window ({age:.1f}s > {MAX_WEBHOOK_AGE_SECONDS}s)")
            except (ValueError, TypeError) as te:
                logger.warning("WebhookManager: Could not parse timestamp '%s': %s", timestamp_header, te)

        # 4. Cryptographic Signature Verification
        sig_header = (
            headers.get("x-hub-signature-256")
            or headers.get("x-signature-256")
            or headers.get("x-signature")
            or headers.get("signature")
        )
        if secret and sig_header:
            is_valid = self.verify_hmac_signature(raw_body, sig_header, secret)
            if not is_valid:
                logger.warning("WebhookManager: Invalid signature for %s (event_id=%s)", provider_name, event_id)
                raise WebhookVerificationException("Cryptographic signature verification failed")
        elif secret and not sig_header:
            # Required secret but signature missing
            logger.warning("WebhookManager: Missing required signature header for %s", provider_name)
            raise WebhookVerificationException("Missing signature header")

        # 5. Idempotency & Anti-Replay Nonce Check
        idempotency_key = f"wh:{provider_name}:{event_id}"
        is_dup, cached_res = await idempotency_manager.check_or_record(idempotency_key, payload)
        if is_dup:
            logger.info("WebhookManager: Duplicate webhook event '%s' detected for %s. Acknowledging without reprocessing.", event_id, provider_name)
            return InboundWebhookResult(
                success=True,
                status="DUPLICATE_ACKNOWLEDGED",
                event_type=payload.get("event_type", "UNKNOWN"),
                event_id=event_id,
                processed=False,
                duplicate=True,
                message="Duplicate webhook event received and acknowledged.",
                normalized_event=cached_res,
            )

        # 6. Execute Handler
        handler = self._handlers.get(provider_key)
        normalized_result: Dict[str, Any] = {}
        if handler:
            try:
                normalized_result = await handler(payload)
            except Exception as he:
                logger.error("WebhookManager: Handler failed for %s (event=%s): %s", provider_name, event_id, he)
                # Enqueue to DLQ
                await dead_letter_service.enqueue(
                    operation_name=f"webhook_process_{provider_name}",
                    integration_id=f"int_{provider_name}",
                    provider_name=provider_name,
                    integration_type=IntegrationType.OTHER,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    attempt_count=1,
                    max_attempts=3,
                    error_code="WEBHOOK_HANDLER_ERROR",
                    error_message=str(he),
                    payload_summary=security_manager.redact_secrets(payload),
                )
                raise he
        else:
            # Generic normalization default
            normalized_result = {
                "provider": provider_name,
                "provider_type": provider_type,
                "event_id": event_id,
                "raw_event_type": payload.get("event_type", "UNKNOWN"),
                "data": payload.get("data", payload),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }

        # Store response in idempotency cache
        await idempotency_manager.store_response(idempotency_key, normalized_result)

        return InboundWebhookResult(
            success=True,
            status="PROCESSED",
            event_type=payload.get("event_type", "UNKNOWN"),
            event_id=event_id,
            processed=True,
            duplicate=False,
            message="Webhook event verified, normalized, and processed successfully.",
            normalized_event=normalized_result,
        )


# Global Singleton
webhook_manager = WebhookManager()
