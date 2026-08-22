# TourSafe — Final System Architecture Map

## 1. System High-Level Architecture

TourSafe is an enterprise-grade tourist safety, risk telemetry, incident response, and emergency orchestration ecosystem built with resilient async pipelines, strict cryptographic auditing, and deterministic safety state machines.

```mermaid
flowchart TB
    subgraph ClientTier [Client Applications Tier]
        TouristApp[Tourist Mobile App - iOS/Android]
        FieldApp[Responder Field Application]
        AuthorityWeb[Authority Command Center Web]
    end

    subgraph GatewayTier [API & Ingress Gateway Tier]
        IngressProxy[Reverse Proxy / TLS 1.3 / WAF]
        RateLimiter[Sliding Window Rate Limiter]
        AuthGuard[JWT Auth & RBAC Validator]
    end

    subgraph ServiceTier [Core Microservice Application Tier]
        TelemetrySvc[Telemetry & Kinematics Service]
        SafetyEngine[Multi-Modal Safety & Risk Fusion]
        EmergencyOrch[Emergency Response Orchestrator]
        RealtimeBus[WebSocket Realtime Hub]
        GovSvc[Governance & Audit Service]
        CopilotSvc[Authority AI Copilot & RAG]
        AnalyticsSvc[Operational Intelligence & Analytics]
    end

    subgraph StorageTier [Data Storage & Resilience Tier]
        MongoCluster[(MongoDB 7.0 Multi-Replica)]
        RedisCluster[(Redis 7.2 Sentinel Cluster)]
        DLQStore[(Dead Letter Queue & Audit Logs)]
    end

    subgraph ExternalTier [External Integration Adapters]
        MapAdapter[Routing & Mapbox/OSRM Adapters]
        CommsAdapter[Twilio SMS & Expo Push]
        CADAdapter[112 Emergency CAD Dispatch]
        WeatherAdapter[OpenWeatherMap Climate Feeds]
    end

    TouristApp --> IngressProxy
    FieldApp --> IngressProxy
    AuthorityWeb --> IngressProxy

    IngressProxy --> RateLimiter --> AuthGuard
    AuthGuard --> TelemetrySvc
    AuthGuard --> SafetyEngine
    AuthGuard --> EmergencyOrch
    AuthGuard --> RealtimeBus
    AuthGuard --> GovSvc
    AuthGuard --> CopilotSvc
    AuthGuard --> AnalyticsSvc

    TelemetrySvc --> SafetyEngine --> EmergencyOrch --> RealtimeBus
    EmergencyOrch --> ExternalTier

    TelemetrySvc --> MongoCluster
    SafetyEngine --> MongoCluster
    EmergencyOrch --> MongoCluster
    GovSvc --> MongoCluster
    CopilotSvc --> MongoCluster
    AnalyticsSvc --> MongoCluster

    RealtimeBus --> RedisCluster
    EmergencyOrch --> DLQStore
```

---

## 2. Architectural Principles & Invariants
1. **Zero Silent Drops**: Every signal, action, and notification is acknowledged or escalated to dead-letter queues.
2. **Idempotency by Design**: All mutating state endpoints require unique idempotency keys (`client_request_id`).
3. **Deterministic Safety State Machine**: Direct uncorroborated state jumps to emergency states are strictly prevented.
4. **Separation of Duties (SoD)**: Security and safety policy configurations cannot be approved by their author.
5. **Data Minimization & Privacy by Design**: Coordinate accuracy is minimized based on current operational context.
