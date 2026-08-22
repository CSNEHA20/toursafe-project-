# TourSafe — Authority Administration & Governance Architecture

## 1. Executive Summary
TourSafe Authority Administration establishes a government-grade administrative and policy governance layer. It allows authorized government agencies, municipal tourism police, disaster response commands, and emergency supervisors to manage organizations, geographic jurisdictions, responders, safety zones, response policies, and platform intelligence without code modifications.

---

## 2. Role-Based Access Control (RBAC) Hierarchy

TourSafe enforces a strict, least-privilege role hierarchy:

| Role | Domain | Permissions & Scope |
| :--- | :--- | :--- |
| `system_admin` | Global / Multi-Tenant | Platform configuration, cross-jurisdiction routing, feature flags, global system health, organization onboarding. |
| `authority_admin` | Agency / Jurisdiction | Jurisdictional policies, responder administrative status, unit capabilities, zone governance, draft configuration authoring. |
| `supervisor` | Operational Oversight | Multi-party policy approval (Separation of Duties), incident command overrides, escalation management. |
| `authority_operator` | Field Dispatch & Queue | Incident acknowledgment, real-time dispatch, responder coordination, operational chat. |
| `responder` | Field Responder | Mission acceptance, GPS navigation, on-scene arrival, status updates, handover. |
| `tourist` | Tourist Experience | Personal safety tracking, SOS activation, digital credentials, itinerary management. |

---

## 3. Organizations & Jurisdictions

### 3.1 Organization Model
Government and municipal public safety agencies are modeled with formal status lifecycles:
- `ACTIVE`: Fully operational with live dispatch authority.
- `SUSPENDED`: Temporarily suspended from creating new policies or field operations.
- `ARCHIVED`: Retained for audit and legal compliance; never hard-deleted.

Supported organization types: `POLICE`, `TOURISM_BOARD`, `EMS`, `MUNICIPAL_SAFETY`, `NATIONAL_PARK`, `DISASTER_MANAGEMENT`, `COAST_GUARD`, `OTHER`.

### 3.2 Geographic Jurisdictions
Jurisdictions bind organizations to geospatial operational territories using RFC 7946 GeoJSON `Polygon` and `MultiPolygon` boundaries:
- **Boundary Validation**: Validates coordinate ranges ($-180 \le \text{lon} \le 180$, $-90 \le \text{lat} \le 90$), closed linear rings (first point equals last point), coordinate winding order, and non-degenerate geometries.
- **Centroid Midpoint**: Automatically calculates representative center coordinates for map viewports.
- **Overlap Conflict Analysis**: Detects spatial intersections across jurisdictions and zones, respecting `cross_jurisdiction_allowed` and `overlap_priority` ranking.

---

## 4. Responder Administrative Governance

TourSafe explicitly decouples administrative status from operational availability:

- **Administrative Status** (`ACTIVE`, `SUSPENDED`, `INACTIVE`): Controlled exclusively by `authority_admin` or `system_admin`.
  - Suspending a responder prevents future incident dispatch assignments.
  - Ongoing field missions are safeguarded (`preserve_ongoing_assignments = True`) to prevent abandoning active emergencies.
- **Operational Status** (`AVAILABLE`, `ASSIGNED`, `RESPONDING`, `ON_SCENE`, `UNAVAILABLE`, `OFFLINE`): Controlled by automated orchestrators and field responder interactions.

---

## 5. Geospatial Safety Zones & Versioning

Geospatial safety zones (`SAFE`, `WARNING`, `RESTRICTED`, `HIGH_RISK`) are version-controlled:
- Any geometric or metadata change produces a new immutable version record.
- Historical incidents and risk episodes retain the exact zone version in effect when the event transpired.
- Overlap conflict analysis prevents conflicting definitions (e.g. `SAFE` tourist promenade overlapping an active `RESTRICTED` hazard area).

---

## 6. Administration Console Modules

1. **Overview Dashboard**: Live counters for active responders, zones, policies, pending approvals, recent audit events, and subsystem health indicators.
2. **Organizations & Jurisdictions**: Boundary editor, GeoJSON importer, and overlap conflict inspector.
3. **User & Role Administration**: Role assignment with privilege escalation guards (non-system admins cannot create system admins).
4. **Policy Governance Center**: Versioned policy authoring, schema validation, multi-party sign-off, atomic activation, and safe rollback.
5. **Simulation Sandbox**: Dry-run execution of escalation graphs and safety risk score models without touching production data.
6. **Immutable Audit Explorer**: Cryptographically hashed audit log viewer with actor, action, and date-range filters.
