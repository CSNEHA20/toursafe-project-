TOURSAFE — PROMPT 4
REAL-TIME COMMUNICATION INFRASTRUCTURE
WEBSOCKET + SOCKET.IO EVENT FOUNDATION
REAL-TIME EVENT BUS
CONNECTION MANAGEMENT
AUTHENTICATED REAL-TIME CHANNELS

============================================================
PROJECT CONTINUATION
============================================================

You are continuing development of the EXISTING TourSafe repository.

Previously completed:

PROMPT 1
- FastAPI backend
- MongoDB
- authentication
- JWT
- role-based authorization

PROMPT 2
- tourist profiles
- authority profiles
- medical profiles
- emergency contacts
- itinerary
- KYC foundation

PROMPT 3
- real zone persistence
- GeoJSON
- zone APIs
- geospatial indexes
- zone audit foundation

DO NOT rebuild those systems.

DO NOT redesign the existing frontend.

DO NOT replace the existing Expo architecture.

DO NOT implement AI anomaly detection yet.

DO NOT implement LSTM yet.

DO NOT collect accelerometer data yet.

DO NOT collect gyroscope data yet.

DO NOT implement real GPS tracking yet.

DO NOT implement geo-fence detection yet.

DO NOT implement SOS orchestration yet.

DO NOT implement DID/blockchain yet.

DO NOT implement e-FIR yet.

This prompt establishes the REAL-TIME COMMUNICATION FOUNDATION that all of those systems will later use.

============================================================
MANDATORY CLAUDE CODE SESSION DOCUMENTATION
============================================================

Every Claude Code prompt/session MUST be permanently documented.

Create:

docs/
└── claude-sessions/
    └── prompt-04-realtime-communication/
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

Store the COMPLETE Prompt 4 text in this file.

Do not summarize it.

------------------------------------------------------------
agent-response.md
------------------------------------------------------------

Store the ACTUAL Claude Code agentic session response.

Record meaningful:

- analysis
- repository inspection
- commands executed
- implementation actions
- terminal outputs
- errors
- fixes
- verification
- final response

Do NOT fabricate an agent response.

Do NOT write a retrospective pretending it is the original session.

If output is extremely large, preserve the relevant command/output transcript and explicitly state where output was abbreviated.

------------------------------------------------------------
work-done.md
------------------------------------------------------------

Document exactly what was implemented.

Separate:

IMPLEMENTED

PARTIALLY IMPLEMENTED

NOT IMPLEMENTED

Do not claim future work as complete.

------------------------------------------------------------
files-changed.md
------------------------------------------------------------

List every:

CREATED
MODIFIED
DELETED

file.

------------------------------------------------------------
verification.md
------------------------------------------------------------

Record actual:

- tests
- type checks
- lint
- backend checks
- WebSocket checks
- Socket.IO checks
- authentication checks
- manual verification

Include actual commands and results.

------------------------------------------------------------
decisions.md
------------------------------------------------------------

Record architectural decisions.

For every important decision:

Decision
Reason
Alternatives considered
Why selected

------------------------------------------------------------
problems-and-solutions.md
------------------------------------------------------------

Record actual implementation problems.

Use:

Problem
Cause
Solution
Verification

If none:

"No significant implementation problems encountered."

============================================================
UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add:

Prompt 4 — Real-Time Communication Infrastructure

Include:

- objective
- status
- major components
- verification
- session folder

============================================================
1. INSPECT EXISTING REALTIME CODE
============================================================

Before modifying anything inspect:

lib/realtime.ts

lib/websocket.ts

lib/api.ts

types/index.ts

store/

backend/

existing Socket.IO code

existing WebSocket code

existing Supabase realtime code

Search the entire repository for:

WebSocket
websocket
Socket.IO
socket.io
realtime
subscribe
unsubscribe
channel
broadcast
emit
onmessage
onopen
onclose

Determine what is currently:

REAL

MOCKED

UNUSED

PARTIALLY IMPLEMENTED

Do not create duplicate realtime systems.

If existing realtime code can be safely extended, preserve it.

If it conflicts with the new architecture, migrate it carefully.

============================================================
2. REAL-TIME ARCHITECTURE
============================================================

Establish this architecture:

                TOURSAFE CLIENTS
                       │
             authenticated connection
                       │
                       ▼
                FASTAPI REALTIME
                       │
             ┌─────────┴─────────┐
             │                   │
       Client channels      Authority channels
             │                   │
             └─────────┬─────────┘
                       │
                  Event Router
                       │
          ┌────────────┼────────────┐
          │            │            │
       MongoDB       Redis      Future AI
       persistence   live state   events
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
              AUTHORITY CLIENTS

The realtime layer must be designed so future modules can publish events without implementing their own independent WebSocket systems.

============================================================
3. CHOOSE ONE PRIMARY REALTIME TRANSPORT
============================================================

Inspect the existing architecture and choose the most appropriate transport.

The project architecture expects:

- FastAPI
- WebSocket telemetry
- Socket.IO-style event distribution

Use the existing project's direction where possible.

If implementing Socket.IO, use a proper Python Socket.IO-compatible server integration with FastAPI/ASGI.

If implementing native WebSockets for telemetry and Socket.IO for dashboard events, clearly separate their responsibilities.

Recommended architecture:

NATIVE WEBSOCKET
----------------
High-frequency telemetry transport.

SOCKET.IO
---------
Low/medium-frequency realtime application events.

Do NOT force 50 Hz telemetry through a UI-oriented event stream.

Do NOT implement telemetry collection yet.

Only establish the transport architecture.

Document the final decision.

============================================================
4. REALTIME EVENT BUS
============================================================

Create a centralized backend realtime event service.

Example conceptual interface:

publish_event()

subscribe_connection()

unsubscribe_connection()

broadcast_to_authority()

send_to_tourist()

broadcast_to_zone()

broadcast_to_user()

Do not scatter:

socket.emit()

or:

websocket.send()

through every router.

Create a central abstraction.

Future modules must be able to do:

publish_event(
    event_type="..."
)

without knowing how clients are connected.

============================================================
5. EVENT ENVELOPE
============================================================

Define one canonical realtime event envelope.

Every event must contain:

event_id

event_type

timestamp

source

version

payload

Example:

{
  "event_id": "...",
  "event_type": "system.status",
  "timestamp": "...",
  "source": "backend",
  "version": 1,
  "payload": {}
}

Do not put arbitrary fields at the top level.

All event-specific information goes inside:

payload

============================================================
6. EVENT TYPES
============================================================

Define a centralized event registry.

Create initial event types for the systems that will eventually exist.

Do NOT implement the underlying functionality yet.

Categories:

SYSTEM

system.connected
system.disconnected
system.status

TOURIST

tourist.profile.updated
tourist.status.updated

LOCATION

location.updated
location.stale

ZONE

zone.created
zone.updated
zone.status_changed

ALERT

alert.created
alert.updated
alert.resolved

SOS

sos.created
sos.updated
sos.resolved

TELEMETRY

telemetry.started
telemetry.stopped
telemetry.status

AI

anomaly.detected
anomaly.confirmed
anomaly.cleared

EMERGENCY

emergency.created
emergency.updated
emergency.dispatched

IDENTITY

identity.verified
identity.access_granted
identity.access_revoked

E-FIR

efir.created
efir.updated
efir.dispatched

Do NOT generate fake events for these.

Only define the event contracts now.

============================================================
7. EVENT VERSIONING
============================================================

Every event must have:

version: 1

Do not make the frontend depend on undocumented payload fields.

Create typed event schemas.

Future changes should be able to introduce:

version 2

without silently breaking version 1 consumers.

============================================================
8. AUTHENTICATED REALTIME CONNECTIONS
============================================================

Realtime connections MUST be authenticated.

Do not allow anonymous authority realtime access.

When a client connects:

1. authenticate token
2. validate token
3. resolve user
4. resolve role
5. create connection context
6. assign appropriate channels
7. send connection acknowledgement

Connection context should include:

connection_id

user_id

role

session_id if applicable

connected_at

============================================================
9. ROLE-BASED CHANNELS
============================================================

Implement logical channels.

TOURIST:

user:{user_id}

TOURIST SESSION:

tourist:{tourist_id}

AUTHORITY:

authority:{authority_id}

AUTHORITY OPERATIONS:

authority:operations

ZONE:

zone:{zone_id}

INCIDENT:

incident:{incident_id}

Do not automatically give every user access to every channel.

Implement authorization rules.

Tourists may access their own channel.

Authorities may access authorized operational channels.

Admins may access broader operational channels.

============================================================
10. CONNECTION MANAGER
============================================================

Create a backend connection manager.

It must track:

active connections

user → connections

role → connections

channel → connections

connection metadata

Handle:

connect

disconnect

reconnect

duplicate connection

stale connection

authentication failure

The system must clean up disconnected connections.

Do not leak connection objects.

============================================================
11. HEARTBEAT / KEEPALIVE
============================================================

Implement connection health management.

Use the chosen realtime transport's proper heartbeat mechanism.

Do not create unnecessary application-level polling if the transport already provides ping/pong.

Expose connection state:

connected

connecting

reconnecting

disconnected

error

The frontend will later use these states.

============================================================
12. FRONTEND REALTIME CLIENT
============================================================

Inspect:

lib/realtime.ts

lib/websocket.ts

and existing frontend stores.

Create or refactor a centralized realtime client.

Do not create one socket per screen.

There must be one managed realtime connection per application session where appropriate.

Expose:

connectRealtime()

disconnectRealtime()

subscribe()

unsubscribe()

getConnectionState()

onEvent()

offEvent()

The client must automatically attach the authentication token.

============================================================
13. FRONTEND EVENT ROUTER
============================================================

Do not put realtime handling directly into individual screens.

Create a centralized event dispatcher.

Conceptually:

Realtime connection
        ↓
Event envelope
        ↓
Event dispatcher
        ↓
Relevant store/service
        ↓
UI

For example:

alert.created
    ↓
alertStore

tourist.profile.updated
    ↓
tourist data store

zone.updated
    ↓
mapStore

location.updated
    ↓
live location store

Do NOT implement location updates yet.

Create the infrastructure so future implementation can plug into it.

============================================================
14. CONNECTION STATUS UI
============================================================

Add a small reusable realtime connection status component.

It should support:

Connected

Connecting

Reconnecting

Offline

Error

Do not create a large dashboard component.

Use the existing TourSafe visual language.

The component should be reusable in:

tourist dashboard

authority dashboard

map

settings

development diagnostics

Do not display technical WebSocket terminology to normal users unless appropriate.

============================================================
15. REALTIME DIAGNOSTIC SCREEN
============================================================

Create a development-only realtime diagnostics screen.

Show:

connection state

connection ID

authenticated user

role

connected at

reconnect count

last event timestamp

events received

events sent

last event type

last error

subscribed channels

This is for development and debugging.

Do not expose it through normal production navigation.

============================================================
16. TEST EVENT ENDPOINT
============================================================

Create a DEVELOPMENT-ONLY mechanism for publishing a test event.

Example:

POST /api/v1/dev/realtime/test-event

This endpoint must:

- be disabled outside development
- require authenticated authorized access
- accept an event type
- accept payload
- publish through the real realtime event bus

Do not use this to generate fake GPS, AI or SOS data.

Its only purpose is validating the realtime infrastructure.

============================================================
17. END-TO-END REALTIME TEST
============================================================

Implement an integration test:

Client A connects.

Client B connects.

Publish a test event.

Verify:

- authorized recipient receives it
- unauthorized recipient does not
- event envelope is correct
- event ID exists
- timestamp exists
- version exists
- payload is correct

Test:

tourist channel

authority channel

zone channel

incident channel

where applicable.

============================================================
18. CONNECTION AUTHORIZATION TESTS
============================================================

Test:

1. valid tourist token
2. valid authority token
3. invalid token
4. expired token
5. missing token
6. tourist attempting authority channel
7. authority accessing operational channel
8. tourist accessing another tourist channel
9. disconnected client cleanup
10. reconnect behavior

Do not mark tests successful without running them.

============================================================
19. REALTIME EVENT SCHEMA TESTS
============================================================

Test that every event contains:

event_id
event_type
timestamp
source
version
payload

Reject malformed events.

Do not allow arbitrary unvalidated event structures.

============================================================
20. REDIS PREPARATION
============================================================

Inspect whether Redis is already configured.

If Redis is available:

create the Redis connection abstraction now.

Do NOT yet implement live GPS storage.

Do NOT yet implement telemetry buffering.

Do NOT yet use Redis as the authoritative event store.

Prepare:

Redis connection
health check
configuration
dependency injection

Future modules will use Redis for:

latest GPS state

connection/session state where appropriate

realtime coordination

Do not overuse Redis.

MongoDB remains the persistent database.

============================================================
21. REALTIME HEALTH CHECK
============================================================

Extend backend health checks.

Expose realtime dependency status.

The health endpoint should be able to report:

backend

mongodb

redis

realtime transport

Do not report:

"healthy"

if a critical dependency is unavailable.

Clearly distinguish:

healthy

degraded

unavailable

============================================================
22. OBSERVABILITY
============================================================

Add structured logs for:

connection established

connection authenticated

connection rejected

connection closed

event published

event delivery failure

subscription denied

reconnect

Do not log:

JWT tokens

passwords

medical information

private keys

full sensitive payloads

Use IDs rather than sensitive information.

============================================================
23. RATE LIMITING / ABUSE PROTECTION
============================================================

Protect realtime connections from obvious abuse.

At minimum establish:

maximum connection/message limits where appropriate

payload size validation

event validation

authentication checks

Do not implement arbitrary aggressive limits that will prevent future 50 Hz telemetry.

Remember:

future telemetry is high-frequency.

The architecture must distinguish:

telemetry transport

from

ordinary application events.

Document the chosen limits.

============================================================
24. FRONTEND MOCK REALTIME
============================================================

Inspect:

lib/realtime.ts

lib/websocket.ts

lib/simulation.ts

lib/useMockApi.ts

Do not allow production realtime behavior to silently use:

random timers

simulated events

fake socket messages

mock subscriptions

The real realtime client must be the production path.

Mock realtime may remain only behind an explicit development/mock flag.

Document remaining mock behavior.

============================================================
25. DO NOT IMPLEMENT THESE FEATURES
============================================================

DO NOT implement:

GPS acquisition

background location

accelerometer

gyroscope

50 Hz telemetry

telemetry windows

LSTM

training datasets

AI inference

geo-fence detection

SOS event creation

automated anomaly confirmation

DID

Polygon

IPFS

dynamic QR

e-FIR

responder routing

FCM

Those belong to later prompts.

This prompt ONLY establishes realtime infrastructure.

============================================================
26. DOCUMENT REALTIME ARCHITECTURE
============================================================

Create:

docs/realtime-architecture.md

Document:

1. realtime transport
2. native WebSocket vs Socket.IO responsibilities
3. authentication
4. connection manager
5. channels
6. event envelope
7. event registry
8. frontend event dispatcher
9. Redis role
10. connection lifecycle
11. heartbeat
12. reconnection
13. security
14. future telemetry integration

Explicitly document:

WHY high-frequency telemetry should not be treated the same way as normal UI events.

============================================================
27. SESSION DOCUMENTATION
============================================================

Before finishing verify:

docs/claude-sessions/prompt-04-realtime-communication/

contains:

prompt.md
agent-response.md
work-done.md
files-changed.md
verification.md
decisions.md
problems-and-solutions.md

agent-response.md MUST represent the actual Claude Code agentic session.

Do not fabricate output.

Record important commands and results.

============================================================
28. UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add Prompt 4.

Include:

Prompt
Objective
Status
Features
Verification
Session path

============================================================
29. VALIDATION
============================================================

Before declaring complete:

Run:

backend tests

frontend type-check

frontend lint

realtime integration tests

authentication tests

Redis health checks if Redis is configured

MongoDB health check

Start backend.

Start MongoDB.

Start Redis.

Start Expo.

Connect a tourist client.

Connect an authority client.

Verify authenticated realtime connection.

Publish development test event.

Verify correct recipient receives it.

Verify unauthorized recipient does not receive it.

Disconnect client.

Verify server cleans connection.

Reconnect.

Verify connection recovery.

Do not claim realtime works without performing an actual end-to-end test.

============================================================
30. FINAL ACCEPTANCE CRITERIA
============================================================

Prompt 4 is complete only when:

- centralized realtime architecture exists
- authenticated realtime connections work
- role-based channels work
- connection manager works
- event envelope exists
- event registry exists
- frontend realtime client exists
- frontend event dispatcher exists
- connection state exists
- development realtime diagnostic exists
- test event works in development
- unauthorized subscriptions are rejected
- disconnect cleanup works
- reconnect works
- Redis integration foundation exists where configured
- health endpoint reports realtime dependencies
- structured realtime logging exists
- no production screen depends on fake realtime behavior
- tests pass
- TypeScript passes
- lint passes
- documentation is complete
- actual agentic session response is documented

============================================================
31. FINAL RESPONSE
============================================================

Return:

IMPLEMENTED

FILES CREATED

FILES MODIFIED

REALTIME ARCHITECTURE

TRANSPORT DECISION

CHANNELS

EVENT TYPES

AUTHENTICATION

REDIS STATUS

FRONTEND INTEGRATION

TEST RESULTS

TYPE CHECK

LINT

MANUAL END-TO-END TEST

MOCK REALTIME STILL USED

KNOWN LIMITATIONS

SESSION DOCUMENTATION

Do not claim GPS, telemetry, AI, geo-fencing or SOS functionality is implemented.

Implement this prompt now.
