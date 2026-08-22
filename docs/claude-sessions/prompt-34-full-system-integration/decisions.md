# Prompt 34 — Architectural & Engineering Decisions

## 1. Release Architecture & Strategy Decisions
1. **Decision: Conclude at `READY_FOR_DEPLOYMENT` rather than fabricated `PRODUCTION_DEPLOYED`**:
   - *Rationale*: Production cloud infrastructure credentials and DNS propagation are external human operator actions. The platform has satisfied 100% of internal integration and verification criteria.
2. **Decision: Zero-Downtime Blue/Green Deployment with 5% Canary Routing**:
   - *Rationale*: Guarantees that active WebSocket connections and tourist tracking feeds are seamlessly migrated without packet drops.
3. **Decision: Single Source of Truth for Database Mocks (`conftest_shared.py`)**:
   - *Rationale*: Fragmented, incomplete mock implementations across individual test files created silent drops and test interdependencies. Unifying mock query semantics ($regex, dot paths, positional updates) ensures deterministic reproducibility.
4. **Decision: Explicit Reset of In-Memory Dynamic Hot-Reload Singletons**:
   - *Rationale*: The safety orchestrator dynamically hot-loads active governance configurations. Restoring default baseline rules at the end of hot-reload tests preserves test isolation for subsequent suites.
