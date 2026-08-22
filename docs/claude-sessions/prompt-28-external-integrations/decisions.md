# Architectural Decisions - Prompt 28: External Integrations & Interoperability Platform

## Key Architectural Decisions

1. **Provider-Independent Adapter Layer**:
   - *Decision*: Core domain logic must never import vendor SDKs or depend on provider response formats.
   - *Rationale*: Protects TourSafe from vendor lock-in, vendor API breaks, and lets operators change providers (e.g. Mapbox to OpenStreetMap) without modifying incident or dispatch services.

2. **Decoupled Circuit Breaker on Each Adapter**:
   - *Decision*: Embed a `CircuitBreaker` instance within each adapter with configurable failure thresholds and recovery cooldowns.
   - *Rationale*: Isolates external provider downtime from slowing down internal request loops, ensuring fast failure and automatic recovery testing in `HALF_OPEN` state.

3. **Dual Storage for Logs, Dead-Letters, and State Conflicts**:
   - *Decision*: Implement dual-storage (in-memory buffer + bounded MongoDB persistence with `asyncio.wait_for` timeout).
   - *Rationale*: Guarantees instant sub-millisecond execution in test/offline environments without blocking when database connectivity is degraded.

4. **Multi-Layer Webhook Defense**:
   - *Decision*: Enforce HMAC-SHA256 signature verification, 300-second timestamp drift rejection, and idempotency key digest checking.
   - *Rationale*: Eliminates spoofed callbacks and network capture replay attacks.

5. **Safety-Critical Token Preservation in Translation**:
   - *Decision*: Regex protect incident IDs (`INC-2026-001`), GPS coordinates, and unit callsigns from translation models.
   - *Rationale*: Prevents LLMs or translation APIs from mangling technical identifiers crucial for emergency dispatch.

6. **Copilot Action Safeguards**:
   - *Decision*: Copilot tools interacting with integrations are strictly read-only by default; write actions (such as Dead-Letter manual retries) require explicit preview and human confirmation.
   - *Rationale*: Prevents automated runaway retries without operator approval.
