# Architecture Decisions — Prompt 11: Safety Orchestration Engine

## 1. Rule Engine Architecture: Pure Determinism (`safety-rules-v1`)
- **Decision**: Implemented a pure, deterministic multi-category rule engine (`safety-rules-v1`) rather than an opaque neural network or non-deterministic LLM.
- **Rationale**: Life safety and incident tracking demand 100% reproducibility and mathematical explainability. Given identical inputs, timestamps, and configurations, the safety decision must be identical and verifiable in court audits.

## 2. Confidence Downgrading & Quality Gating
- **Decision**: When GPS accuracy is $> 50\text{m}$ or telemetry sample frequency is degraded ($< 35\text{Hz}$), the safety engine automatically sets `confidence_class = LOW` and enforces a hard ceiling of `ELEVATED`, preventing candidate or incident states unless corroborated by high-confidence auxiliary signals.
- **Rationale**: Prevents spurious false alarms caused by noisy mobile sensors, urban canyon multipath reflections, or operating system battery throttle artifacts.

## 3. Strict Distinction Between No Risk and No Data
- **Decision**: Missing signals or disconnected tracking sessions strictly yield `SafetyState.UNKNOWN` with `SignalQuality.MISSING`, rather than defaulting to `NORMAL`.
- **Rationale**: An unmonitored tourist whose phone has died in a canyon cannot be assumed safe. Operational authorities must immediately see `UNKNOWN` to trigger check-in protocols.

## 4. Two-Phase Confirmation for Incidents (`INCIDENT_CANDIDATE` $\to$ `INCIDENT`)
- **Decision**: An incident requires passing through `INCIDENT_CANDIDATE` and confirming on a consecutive cycle before escalating to `INCIDENT` (unless corroborated by high-severity persistence + danger zone).
- **Rationale**: Filters out transient multi-sensor spikes and enforces temporal hysteresis.

## 5. 20-Second Recovery Cooldown Period
- **Decision**: Returning to `NORMAL` from an active incident requires a 20-second stable period in `RECOVERING`.
- **Rationale**: Prevents high-frequency state flapping between `INCIDENT` and `NORMAL` during intermittent sensor recovery.
