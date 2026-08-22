# Provider Adapter Development & Registration Guide

This guide walks developers through implementing and registering a new third-party provider adapter in TourSafe.

---

## 1. Adapter Contract Rules

When creating a new provider adapter:
1. **Extend `IntegrationAdapter`**: Inherit from `app.services.integrations.adapters.base.IntegrationAdapter`.
2. **Never import vendor SDKs in Core**: Vendor SDKs or HTTP client libraries must remain confined entirely inside the adapter file.
3. **Declare Supported Capabilities**: Populate `capabilities` list (e.g. `["geocoding", "routing"]`).
4. **Implement Lifecycle**:
   - `async def initialize(self) -> None`: Initialize connection pools or SDK credentials.
   - `async def shutdown(self) -> None`: Clean up resources on server shutdown.
   - `async def execute_health_check(self) -> IntegrationHealthStatus`: Test live upstream connectivity.
5. **Enforce Circuit Breaker Pre-execution**: Call `await self.circuit_breaker.before_execution()` before making upstream calls.
6. **Record Latency & Health**: Call `self.record_request_metrics(latency_ms, is_success=True/False)`.
7. **Normalize Upstream Errors**: Convert vendor-specific error codes into standard `IntegrationErrorCode` values.

---

## 2. Example: Implementing a Custom SMS Adapter

```python
from typing import Any, Dict, List, Optional
import time
from app.schemas.integrations import IntegrationConfig, IntegrationHealthStatus, IntegrationType
from app.services.integrations.adapters.base import IntegrationAdapter

class CustomSMSAdapter(IntegrationAdapter):
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(
            provider_name="CUSTOM_CARRIER_SMS",
            integration_type=IntegrationType.SMS,
            is_real_provider=True,
            config=config,
        )

    @property
    def capabilities(self) -> List[str]:
        return ["sms_send", "delivery_receipt", "unicode_support"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.is_healthy = True
        status.detail = "Carrier gateway reachable"
        return status

    async def send_sms(self, recipient_phone: str, message_body: str) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        try:
            # Vendor specific HTTP call or SDK invocation here
            provider_msg_id = "custom_sms_12345"
            
            latency_ms = (time.time() - start_t) * 1000.0
            await self.circuit_breaker.record_success()
            self.record_request_metrics(latency_ms, is_success=True)

            return {
                "success": True,
                "status": "SENT",
                "provider": self.provider_name,
                "provider_message_id": provider_msg_id,
            }
        except Exception as e:
            latency_ms = (time.time() - start_t) * 1000.0
            await self.circuit_breaker.record_failure(e)
            self.record_request_metrics(latency_ms, is_success=False)
            raise e
```

---

## 3. Registering the Adapter

Register your adapter in `IntegrationRegistry`:

```python
from app.services.integrations.registry import integration_registry

custom_sms = CustomSMSAdapter()
integration_registry.register_adapter(custom_sms, is_primary=False)
```
