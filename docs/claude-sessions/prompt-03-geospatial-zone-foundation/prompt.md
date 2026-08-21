TOURSAFE — PROMPT 3
REAL GEOSPATIAL ZONE FOUNDATION
GEOJSON ZONES
ZONE MANAGEMENT
MAP-READY APIs
AUTHORITY ZONE OPERATIONS

============================================================
IMPORTANT — CONTINUE THE EXISTING PROJECT
============================================================

You are continuing development of the EXISTING TourSafe repository.

Prompt 1:
Backend foundation + authentication

Prompt 2:
Tourist + authority profiles
Medical information
Emergency contacts
Itinerary
KYC foundation

have already been implemented.

DO NOT rebuild those systems.

DO NOT rewrite the existing authentication architecture.

DO NOT introduce mock zone data as the production source.

DO NOT implement AI anomaly detection yet.

DO NOT implement LSTM yet.

DO NOT implement accelerometer/gyroscope telemetry yet.

DO NOT implement live GPS streaming yet.

DO NOT implement automatic geo-fence detection yet.

This prompt establishes the REAL geospatial zone foundation that the future GPS and geo-fencing systems will consume.

============================================================
MANDATORY AGENTIC SESSION DOCUMENTATION
============================================================

This is a mandatory requirement for EVERY Claude Code session.

For this prompt create:

docs/
└── claude-sessions/
    └── prompt-03-geospatial-zone-foundation/
        ├── prompt.md
        ├── agent-response.md
        ├── work-done.md
        ├── files-changed.md
        ├── verification.md
        ├── decisions.md
        └── problems-and-solutions.md

------------------------------------------------------------
prompt.md
------------------------------------------------------------

Copy the COMPLETE Prompt 3 instructions into:

prompt.md

Do not summarize the prompt.

Store the actual prompt.

------------------------------------------------------------
agent-response.md
------------------------------------------------------------

This file MUST contain the actual Claude Code agentic session response/output.

Record:

- Claude's initial analysis
- commands Claude executed
- important inspection findings
- implementation progress
- test results
- errors encountered
- fixes performed
- final response

Do NOT fabricate this content.

Do NOT write a generic summary.

Record the actual agent response/session output available during the session.

If the terminal output is extremely large, preserve the meaningful command/result transcript and explicitly state where output was abbreviated.

------------------------------------------------------------
work-done.md
------------------------------------------------------------

Document what was ACTUALLY implemented.

Separate:

IMPLEMENTED

PARTIALLY IMPLEMENTED

NOT IMPLEMENTED

Do not describe planned functionality as completed functionality.

------------------------------------------------------------
files-changed.md
------------------------------------------------------------

List:

CREATED
MODIFIED
DELETED

for every file touched during this prompt.

------------------------------------------------------------
verification.md
------------------------------------------------------------

Record actual:

- backend tests
- frontend tests
- type checking
- linting
- API tests
- database tests
- GeoJSON validation
- manual verification

Include commands and actual results.

------------------------------------------------------------
decisions.md
------------------------------------------------------------

Record important architecture decisions made during this session.

For each:

Decision
Reason
Alternative considered
Why chosen

------------------------------------------------------------
problems-and-solutions.md
------------------------------------------------------------

Record actual problems encountered during implementation and how they were resolved.

If no significant problems occurred, explicitly write:

"No significant implementation problems encountered."

============================================================
UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add:

Prompt 3 — Real Geospatial Zone Foundation

Include:

- objective
- implementation status
- session folder
- major features
- verification status

============================================================
1. INSPECT EXISTING TOURSAFE CODE
============================================================

Before implementation inspect:

app/tourist/(tabs)/map.tsx

app/admin/(tabs)/map.tsx

app/admin/(tabs)/zones.tsx

lib/api.ts

lib/mapStore.ts

types/index.ts

store/mapStore.ts

existing zone-related components

existing mockData.ts

existing simulation.ts

existing map configuration

existing backend routers/models/schemas

Determine exactly how zones are currently represented.

Do not create duplicate zone models.

If an existing zone schema exists, extend it carefully.

Preserve existing UI.

============================================================
2. REAL ZONE DATA MODEL
============================================================

Create a persistent MongoDB Zone model.

The Zone entity must support:

zone_id

name

description

zone_type

risk_level

status

boundary

center

properties

is_active

created_at

updated_at

created_by

updated_by

Use explicit enumerations.

zone_type:

safe
warning
restricted

risk_level:

low
medium
high
critical

status:

active
inactive
draft

Do not use arbitrary strings throughout the application.

Use strongly typed enums where appropriate.

============================================================
3. GEOJSON BOUNDARIES
============================================================

Zone boundaries MUST be represented using GeoJSON-compatible geometry.

The primary geometry should be:

Polygon

Support MultiPolygon if the architecture requires it.

Use the standard GeoJSON structure:

{
  "type": "Polygon",
  "coordinates": [...]
}

Coordinates MUST follow GeoJSON order:

[longitude, latitude]

NOT:

[latitude, longitude]

This distinction is critical.

Document this explicitly in:

docs/claude-sessions/prompt-03-geospatial-zone-foundation/decisions.md

============================================================
4. GEOJSON VALIDATION
============================================================

Implement backend validation for zone geometry.

Validate:

- geometry type
- coordinate structure
- longitude range
- latitude range
- minimum polygon structure
- closed polygon rings
- valid coordinate nesting

Reject malformed GeoJSON.

Do not silently repair invalid geometry.

Return a clear validation error.

Where practical, use a proper geospatial validation library rather than writing a fragile custom geometry parser.

============================================================
5. ZONE CENTER
============================================================

Store a representative center point for every zone.

Represent it as GeoJSON Point:

{
  "type": "Point",
  "coordinates": [longitude, latitude]
}

Do not calculate or store:

latitude first

longitude second

Document coordinate ordering.

============================================================
6. TOURSAFE INITIAL ZONES
============================================================

The existing TourSafe frontend/documentation contains zone concepts such as:

- Berijam Lake Forest Reserve
- Pillar Rocks Viewpoint
- Ooty Botanical Gardens
- Ooty Lake & Boathouse
- Doddabetta Peak Summit
- Guna Caves
- Coaker's Walk
- Vattakanal

Inspect the existing project and source documents before creating these records.

Where the project already defines exact zone descriptions/statuses, preserve those definitions.

DO NOT invent precise geographic boundaries if the project source does not provide them.

If real coordinates/boundaries are unavailable in the existing source:

create a clearly marked development dataset

and label it:

DEVELOPMENT GEOMETRY

Do not present invented boundaries as authoritative real-world boundaries.

============================================================
7. ZONE CRUD API
============================================================

Implement real FastAPI endpoints.

Authority/admin access:

POST /api/v1/authority/zones

GET /api/v1/authority/zones

GET /api/v1/authority/zones/{zone_id}

PATCH /api/v1/authority/zones/{zone_id}

DELETE /api/v1/authority/zones/{zone_id}

Public/authenticated map consumption:

GET /api/v1/zones

GET /api/v1/zones/{zone_id}

The exact route structure may be adapted to the existing backend conventions, but maintain clear separation between:

authority management

and

tourist consumption.

============================================================
8. AUTHORIZATION
============================================================

Only:

admin

and appropriately authorized authority users

may create/update/delete zones.

Tourists must NOT be able to modify zones.

A normal tourist may only retrieve zones that are active and published.

Do not trust frontend role state.

Authorization must be enforced on the backend.

============================================================
9. ZONE SEARCH AND FILTERING
============================================================

Authority zone listing must support:

search by name

filter by:

status

zone_type

risk_level

pagination

sorting

Tourist-facing zone listing should support:

active zones

zone_type

risk_level

Do not load an unlimited number of records.

============================================================
10. ZONE VERSION / AUDIT FOUNDATION
============================================================

Zone boundaries are safety-critical data.

Do not silently overwrite important geometry changes.

Create an audit mechanism for zone modifications.

Record:

zone_id

action

changed_by

changed_at

previous values where practical

new values where practical

Actions:

created

updated

boundary_updated

status_changed

deleted

This is a foundation for future authority audit trails.

============================================================
11. ZONE STATUS MANAGEMENT
============================================================

Implement explicit status transitions.

Examples:

draft → active

active → inactive

inactive → active

Do not allow arbitrary invalid transitions without validation.

When a zone changes:

safe → warning

warning → restricted

etc.

Record the change in the zone audit log.

Do not yet automatically change zone status from AI or GPS.

That comes later.

============================================================
12. TOURIST MAP API
============================================================

Create a map-friendly endpoint that returns active zones in a frontend-ready format.

Example conceptual response:

{
  "zones": [
    {
      "zone_id": "...",
      "name": "...",
      "type": "warning",
      "risk_level": "medium",
      "geometry": {
        "type": "Polygon",
        "coordinates": [...]
      },
      "center": {
        "type": "Point",
        "coordinates": [...]
      }
    }
  ]
}

Do not return unnecessary internal database fields.

This endpoint will later be consumed by:

tourist map

authority map

geo-fencing engine

============================================================
13. UPDATE EXISTING TOURIST MAP
============================================================

Inspect:

app/tourist/(tabs)/map.tsx

Replace static/mock zone information with the real:

GET /api/v1/zones

API.

Do not yet implement automatic geofence detection.

The map should simply render the real zone polygons.

Implement:

loading

success

empty

error

retry

states.

============================================================
14. UPDATE EXISTING AUTHORITY MAP
============================================================

Inspect:

app/admin/(tabs)/map.tsx

Connect it to the real zone API.

Render:

zone boundaries

zone names

risk levels

zone status

Do not yet implement live tourist GPS.

Do not use simulated tourist markers as the source of truth for this prompt.

If the existing authority map contains mock tourist markers, leave them isolated and clearly label them as temporary until the real location pipeline is implemented.

============================================================
15. UPDATE AUTHORITY ZONES SCREEN
============================================================

Inspect:

app/admin/(tabs)/zones.tsx

Replace mock zone records with real API data.

Implement:

list

search

filter

view details

create zone

edit zone

change status

delete/deactivate zone

Use the existing visual design.

Do not redesign the entire screen.

============================================================
16. ZONE CREATION UI
============================================================

Create a functional authority-side zone creation workflow.

Fields:

name

description

zone type

risk level

status

boundary geometry

center

The authority must be able to provide GeoJSON geometry.

If the existing UI supports map drawing, integrate with that.

If the existing UI does NOT support polygon drawing yet:

create a structured GeoJSON input/editor for development

and keep the architecture ready for interactive map drawing later.

Do not fake polygon creation.

============================================================
17. ZONE EDITING
============================================================

Allow authority users to modify:

name

description

type

risk level

status

boundary

center

Every successful update must persist to MongoDB.

Every important update must create an audit record.

============================================================
18. ZONE DETAIL VIEW
============================================================

Zone detail must display:

Zone name

Description

Type

Risk level

Status

Boundary

Center coordinates

Created at

Updated at

Created by

Updated by

Audit history where authorized.

Do not expose internal database identifiers unnecessarily to tourists.

============================================================
19. MAP DATA FORMAT
============================================================

Create shared TypeScript types for:

Zone

ZoneGeometry

GeoJSONPoint

GeoJSONPolygon

GeoJSONMultiPolygon

ZoneType

ZoneRiskLevel

ZoneStatus

Keep frontend and backend contracts consistent.

Do not define slightly different zone structures in:

types/index.ts

API responses

map components

backend schemas

Create one canonical contract wherever practical.

============================================================
20. GEOSPATIAL INDEXING
============================================================

Use MongoDB geospatial indexes appropriately.

If the chosen MongoDB schema supports GeoJSON queries, configure the required:

2dsphere

index.

At minimum consider indexing:

boundary

center

Do not add geospatial indexes blindly if the chosen MongoDB representation does not support the operation.

Verify the indexes actually exist.

============================================================
21. PREPARE FOR FUTURE GEO-FENCING
============================================================

Do NOT implement geo-fencing detection yet.

However, design the zone representation so the future engine can perform:

point-in-polygon

zone entry

zone exit

zone transition

risk evaluation

The future pipeline will be:

GPS position
      ↓
Zone lookup
      ↓
Point-in-polygon
      ↓
Current zone
      ↓
Previous zone
      ↓
Entry/exit detection
      ↓
Safety event

This prompt only builds the data foundation required for that pipeline.

============================================================
22. PREPARE FOR FUTURE LIVE GPS
============================================================

Do not implement live GPS in this prompt.

But make sure the zone API can later support:

GET nearby zones

or geospatial queries based on:

latitude

longitude

radius

Do not prematurely implement Redis live GPS.

That will be handled in a later prompt.

============================================================
23. REMOVE PRODUCTION ZONE MOCK DEPENDENCY
============================================================

Inspect:

lib/mockData.ts

lib/simulation.ts

lib/useMockApi.ts

Find every zone-related mock.

After this prompt:

Production mode must retrieve zones from FastAPI.

Mock zone data may remain only behind explicit development/mock configuration.

Do not silently merge mock zones with real zones.

============================================================
24. ERROR HANDLING
============================================================

Create meaningful backend errors for:

invalid GeoJSON

zone not found

duplicate zone

unauthorized modification

invalid status transition

invalid risk level

invalid zone type

invalid coordinates

Do not expose stack traces.

============================================================
25. TESTING
============================================================

Create backend tests for:

1. create zone
2. retrieve zone
3. list zones
4. update zone
5. delete/deactivate zone
6. tourist cannot modify zone
7. authority can modify zone
8. invalid GeoJSON rejected
9. invalid coordinates rejected
10. polygon ring validation
11. zone filtering
12. zone pagination
13. zone search
14. geospatial index existence
15. audit record creation
16. status transition validation

Test GeoJSON carefully.

Include tests for:

Point

Polygon

invalid polygon

latitude > 90

latitude < -90

longitude > 180

longitude < -180

unclosed polygon ring

incorrect coordinate nesting

============================================================
26. FRONTEND VERIFICATION
============================================================

Verify:

Tourist Map

Authority Map

Authority Zones

Zone Details

Zone Creation

Zone Editing

Zone Status

Verify that the UI is reading real MongoDB-backed API data.

Verify that creating a zone from the authority interface causes the new zone to appear on:

Authority zone list

Authority map

Tourist map

after successful API retrieval.

Do not rely on local React state as the permanent source of truth.

============================================================
27. DO NOT IMPLEMENT FUTURE FEATURES
============================================================

DO NOT implement:

accelerometer

gyroscope

telemetry

50Hz sensor stream

GPS background tracking

Redis live GPS

WebSocket telemetry ingestion

LSTM

AI anomaly detection

training datasets

model inference

geo-fence event detection

SOS orchestration

DID

Polygon

IPFS

dynamic QR

e-FIR

nearest responder routing

FCM

Those will be separate prompts.

============================================================
28. DOCUMENTATION
============================================================

Create/update:

docs/geospatial-architecture.md

Document:

- Zone model
- GeoJSON representation
- coordinate ordering
- zone status
- zone types
- risk levels
- API endpoints
- MongoDB geospatial indexes
- audit mechanism
- future geo-fencing integration

Clearly separate:

IMPLEMENTED IN PROMPT 3

from

FUTURE GEO-FENCING ENGINE

============================================================
29. CLAUDE SESSION RECORD
============================================================

Before finishing:

Ensure the following exist:

docs/claude-sessions/prompt-03-geospatial-zone-foundation/

prompt.md
agent-response.md
work-done.md
files-changed.md
verification.md
decisions.md
problems-and-solutions.md

IMPORTANT:

agent-response.md must contain the ACTUAL agentic response/session record.

It must NOT be a generated retrospective pretending to be the original response.

Include actual commands and meaningful outputs.

If Claude encountered an error and fixed it, record:

ERROR
CAUSE
FIX
VERIFICATION

============================================================
30. UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add Prompt 3.

Include:

Prompt number

Name

Status

Date

Major features

Verification status

Session documentation path

============================================================
31. FINAL VALIDATION
============================================================

Before declaring Prompt 3 complete:

Run:

backend tests

frontend type-check

frontend lint

GeoJSON tests

MongoDB index verification

API endpoint tests

Start FastAPI.

Start MongoDB.

Start Expo.

Verify:

1. Authority can create a zone.
2. Zone is persisted in MongoDB.
3. Zone appears in authority zone list.
4. Zone appears on authority map.
5. Zone appears on tourist map.
6. Authority can edit zone.
7. Audit entry is created.
8. Tourist cannot modify zone.
9. Invalid GeoJSON is rejected.
10. Search works.
11. Filters work.
12. Pagination works.
13. No production screen silently falls back to mock zones.

Fix all discovered issues before finishing.

============================================================
32. FINAL RESPONSE
============================================================

Your final response must contain:

IMPLEMENTED

FILES CREATED

FILES MODIFIED

API ENDPOINTS

DATABASE COLLECTIONS

GEOJSON FORMAT

GEOSPATIAL INDEXES

AUTHORIZATION

AUDIT SYSTEM

TEST RESULTS

TYPE CHECK RESULT

LINT RESULT

MANUAL VERIFICATION

MOCK DATA STILL USED

KNOWN LIMITATIONS

SESSION DOCUMENTATION LOCATION

IMPORTANT:

Do not say that geo-fencing is implemented.

At this stage we have only created the geospatial zone foundation.

Do not claim GPS integration.

Do not claim AI integration.

Do not claim real-time location integration.

Implement this prompt now.
