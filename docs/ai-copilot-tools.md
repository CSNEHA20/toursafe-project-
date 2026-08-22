# TourSafe Authority AI Copilot Tool Catalog

The AI Copilot operates through a strictly permission-gated, schema-validated tool calling registry. Raw SQL, MongoDB queries, or arbitrary command execution are architecturally prevented.

---

## Tool Registry Overview

| Category | Tool Name | Allowed Roles | Description | Side Effects |
| :--- | :--- | :--- | :--- | :--- |
| **Incidents** | `get_active_incidents` | `authority`, `admin` | Fetches active incidents with severity, type, and location filters | None (Read-only) |
| **Incidents** | `get_incident_details` | `authority`, `admin` | Retrieves full incident record, timeline events, and assigned responders | None (Read-only) |
| **Safety** | `get_safety_summary` | `authority`, `admin` | Summarizes active alerts, high-risk tourists, and safe zones | None (Read-only) |
| **Safety** | `get_tourists_in_risk_zones` | `authority`, `admin` | Identifies tourists currently situated in danger or restricted zones | None (PII Redacted) |
| **Risk** | `get_risk_episodes` | `authority`, `admin` | Queries active anomaly episodes and risk score spikes | None (Read-only) |
| **Risk** | `explain_risk_score` | `authority`, `admin` | Breaks down ML risk score features and reason codes | None (Read-only) |
| **Zones** | `get_zone_status` | `authority`, `admin` | Retrieves real-time safety status, tourist count, and active restrictions | None (Read-only) |
| **Zones** | `list_safety_zones` | `authority`, `admin` | Lists all geofenced zones with risk tiers and polygon boundaries | None (Read-only) |
| **Tourists** | `get_tourist_safe_overview` | `authority`, `admin` | Aggregates tourist count, nationality distributions, and active journeys | None (PII Redacted) |
| **Tourists** | `find_tourist_by_identifier` | `authority`, `admin` | Searches for tourist record by pseudonymized ID or KYC handle | None (PII Redacted) |
| **Responders** | `get_available_responders` | `authority`, `admin` | Finds active emergency responders, units, capabilities, and battery/signal status | None (Read-only) |
| **Responders** | `get_responder_location` | `authority`, `admin` | Obtains latest GPS fix and distance to target coordinates | None (Read-only) |
| **Analytics** | `get_operational_analytics` | `authority`, `admin` | Retrieves incident resolution rates, SLA compliance, and dispatch duration percentiles | None (Read-only) |
| **Analytics** | `get_incident_heatmap_data` | `authority`, `admin` | Generates geohash-clustered incident density data with k-anonymity | None (Read-only) |
| **Policies** | `get_response_policies` | `authority`, `admin` | Fetches operational policies, escalation matrices, and SLA thresholds | None (Read-only) |
| **Policies** | `search_knowledge_base` | `authority`, `admin` | Hybrid semantic + keyword retrieval over approved SOPs and manuals | None (Read-only) |
| **Health** | `get_system_health` | `authority`, `admin` | Evaluates MongoDB, Redis, WebSocket bus, and worker queue health | None (Read-only) |
| **Plans** | `get_active_response_plans` | `authority`, `admin` | Queries currently executing automated response plans and step statuses | None (Read-only) |
| **Action Proposals** | `propose_dispatch_responder` | `authority`, `admin` | Generates structured preview card to dispatch responder with token | Generates Action Proposal |
| **Action Proposals** | `propose_zone_alert` | `authority`, `admin` | Generates preview card to broadcast safety alert to zone | Generates Action Proposal |
| **Action Proposals** | `propose_escalation` | `authority`, `admin` | Generates preview card to escalate incident to Stage 2/3 supervisor | Generates Action Proposal |

---

## Security & Protection Guardrails

1. **Loop Detection**: Max 5 tool calls per conversational turn. Repeating identical tool calls with identical arguments triggers immediate execution halt.
2. **Execution Timeout**: Tools execute under bounded timeouts (default: 10,000ms).
3. **PII Sanitization**: Every tool returning tourist or contact information passes data through `_sanitize_pii()` to mask phone numbers (`+91 98****3210`), email addresses (`t***t@example.com`), and identity numbers (`IND-****-4321`).
4. **Input Validation**: Argument validation via Pydantic and regex sanitization to strip prompt injection payloads.
