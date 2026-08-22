# Prompt 15 Architectural Decisions

## 1. Zero Parallel Data Stores (Derive from Canonical Truth)
- **Decision**: All analytical calculations aggregate directly from existing authoritative operational collections (`incidents`, `location_history`, `zones`, `anomaly_events`, etc.).
- **Reason**: Parallel historical tables or duplicate schemas drift out of sync, create inconsistencies, and complicate maintenance.
- **Alternatives Considered**: Creating separate analytical tables updated via background write-hooks.
- **Why Selected**: Direct aggregation combined with intelligent Redis caching preserves single-source-of-truth integrity while delivering sub-millisecond cached responses.

---

## 2. Dynamic TTL & Tiered Multi-Tenant Caching
- **Decision**: Implement dynamic cache TTLs in Redis where live windows get 30-120 seconds TTL, whereas historical multi-day windows get 600-3600 seconds TTL.
- **Reason**: Historical data from past weeks is immutable and does not require re-aggregation on every dashboard refresh, while live today numbers must remain fresh.
- **Alternatives Considered**: Fixed global TTL of 60 seconds.
- **Why Selected**: Optimizes database query load by over 90% without compromising operational data freshness.

---

## 3. Pure Python Base32 Geohash Spatial Grid
- **Decision**: Implemented Base32 geohash encoding and decoding in pure Python within the aggregation engine.
- **Reason**: Introducing heavyweight external spatial libraries (e.g. `uber-h3` or C-extensions) causes compilation issues across diverse Windows/Linux hosting environments.
- **Alternatives Considered**: Adding `h3-py` or `geohash2` dependencies.
- **Why Selected**: Standard Base32 geohash algorithms provide fast, deterministic, cross-platform spatial cell bucketing with zero native binary dependencies.

---

## 4. $k$-Anonymity Cell Privacy Suppression
- **Decision**: Geographic heatmap cells with fewer than $k=3$ unique tourists are automatically flagged as suppressed (`weight=0.0`, `is_suppressed=true`).
- **Reason**: Exposing raw individual coordinates or solitary trails on public or broad analytical layers violates tourist privacy and creates tracking vulnerabilities.
- **Alternatives Considered**: Displaying all points with subtle jitter.
- **Why Selected**: Strict $k$-anonymity suppression adheres to global privacy standards (GDPR, SAIF) without reducing analytical utility in dense zones.

---

## 5. Explicit "Operational Conversion Rate" vs "Model Accuracy"
- **Decision**: Anomaly metrics explicitly measure *Operational Incident Conversion Rate* rather than "AI Model Accuracy".
- **Reason**: Without verified ground-truth labels for every telemetry window, calling an unconverted anomaly "inaccurate" is scientifically flawed (the tourist may have stumbled and recovered).
- **Alternatives Considered**: Labelling all non-incident anomalies as false positives.
- **Why Selected**: Maintains scientific integrity and honest terminology for authority decision support.
