# Prompt 7: Architectural Decisions

## Decision 1: No Synthetic GPS Coordinate Fabrication
- **Decision**: GPS observations (~1 Hz) are attached as `gps_context` using the nearest valid observation within the 3.0s window buffer.
- **Rationale**: Linear interpolation across mountain roads or tight turns creates fake coordinates that could falsely trigger boundary alerts. Real sensor readings must be preserved unaltered.

## Decision 2: Decoupled Ingestion Queue & Drain-Based Background Worker
- **Decision**: Ingested packets are pushed into an in-memory bounded `asyncio.Queue(maxsize=5000)`. A worker drains and persists to MongoDB.
- **Rationale**: High-frequency 50 Hz packets should not block HTTP or WebSocket request-response lifecycles. If the worker queue is full, bounded drop prevents unbounded memory growth.

## Decision 3: Contiguous Watermark Acknowledgment Protocol
- **Decision**: Acknowledgment envelopes return `highest_contiguous_sequence` rather than just the single received sequence number.
- **Rationale**: Allows the mobile client to safely prune all acknowledged packets in its local AsyncStorage offline buffer in one O(1) operation without tracking per-packet state tables.

## Decision 4: Operational Privacy & Authority Channel Protection
- **Decision**: Raw 50 Hz triaxial IMU streams are strictly kept off authority broadcast channels (`authority:operations`). Only aggregated summaries (`telemetry.status.updated`) and overall quality metrics are exposed.
- **Rationale**: Protects tourist physical privacy and avoids overwhelming mobile/web dashboard network bandwidth with high-frequency raw sensor streams.
