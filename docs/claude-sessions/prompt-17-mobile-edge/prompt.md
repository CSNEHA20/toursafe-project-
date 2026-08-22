PROMPT 17
MOBILE EDGE & SENSOR INTELLIGENCE
REAL DEVICE TELEMETRY

============================================================
PROJECT CONTINUATION
============================================================

You are continuing development of the EXISTING TourSafe repository.

Previously completed:

PROMPT 1
- backend foundation
- MongoDB
- authentication
- JWT
- RBAC

PROMPT 2
- tourist profiles
- authority profiles
- emergency contacts
- itinerary
- KYC foundation

PROMPT 3
- GeoJSON zones
- geospatial database
- zone management
- geospatial indexes

PROMPT 4
- authenticated realtime communication
- realtime event architecture
- event envelope
- event registry
- Redis

PROMPT 5
- real GPS
- foreground/background tracking
- tracking sessions
- location history
- realtime location updates

PROMPT 6
- real accelerometer
- real gyroscope
- synchronized IMU telemetry
- target high-frequency sampling
- sensor quality

PROMPT 7
- telemetry ingestion
- Redis live telemetry
- MongoDB telemetry
- offline buffering
- idempotency
- sequence handling
- telemetry windows
- quality metrics

PROMPT 8
- LSTM autoencoder
- preprocessing
- dataset splitting
- model training
- threshold calibration
- model artifacts

PROMPT 9
- realtime LSTM inference
- anomaly state machine
- anomaly events
- anomaly history

PROMPT 10
- real GPS geofencing
- GeoJSON
- zone entry
- zone exit
- dwell
- GPS accuracy
- stale GPS

PROMPT 11
- safety signal aggregation
- anomaly + geofence + GPS + telemetry
- deterministic safety rules
- safety state machine
- incident generation

PROMPT 12
- SOS
- incident lifecycle
- acknowledgement
- assignment
- escalation
- resolution
- closure

PROMPT 13
- responder accounts
- responder units
- capabilities
- responder GPS
- responder tracking
- assignment
- responder communication

PROMPT 14
- notification infrastructure
- realtime notifications
- push/SMS/email/voice abstractions
- delivery tracking
- retry engine
- dead-letter
- notification policies

PROMPT 15
- tourist analytics
- trip analytics
- zone analytics
- incident analytics
- anomaly analytics
- responder analytics
- response KPIs
- data-quality analytics
- heatmaps

PROMPT 16
- ML dataset pipeline
- dataset versioning
- feature versioning
- training pipeline
- experiment tracking
- model registry
- model approval
- staging
- shadow
- canary
- production model management
- rollback
- drift detection

NOW IMPLEMENT:

THE MOBILE EDGE & SENSOR INTELLIGENCE LAYER.

============================================================
CORE OBJECTIVE
============================================================

Make TourSafe's mobile telemetry pipeline reliable on a REAL DEVICE.

The mobile application must support:

GPS
+
ACCELEROMETER
+
GYROSCOPE
+
NETWORK STATE
+
BATTERY STATE
+
BACKGROUND EXECUTION
+
LOCAL BUFFER
+
SERVER SYNCHRONIZATION

The system must continue functioning gracefully when:

network disappears

GPS becomes unavailable

sensor becomes unavailable

application enters background

device battery becomes low

mobile OS restricts background execution

device restarts

server becomes temporarily unavailable.

============================================================
CRITICAL PRINCIPLE
============================================================

The phone is:

A SENSOR AND DATA COLLECTION EDGE NODE.

The phone is NOT:

the authoritative safety decision engine.

Mobile may perform:

collection

validation

buffering

lightweight preprocessing

connectivity management

health checks.

Backend remains authoritative for:

safety state

incident state

geofencing decisions where server-authoritative

LSTM production inference

model version

emergency workflow.

============================================================
STRICT SCOPE
============================================================

Implement:

- mobile sensor service
- GPS service
- accelerometer service
- gyroscope service
- sensor lifecycle
- tracking session lifecycle
- background tracking
- foreground tracking
- local telemetry queue
- offline-first buffering
- batch upload
- retry
- idempotency
- sequence numbers
- timestamp handling
- GPS/IMU synchronization
- adaptive sampling
- battery-aware behavior
- connectivity awareness
- device health
- sensor health
- telemetry health
- server synchronization
- app restart recovery
- tracking recovery
- permissions handling
- user controls
- privacy controls
- telemetry diagnostics
- mobile telemetry status UI

DO NOT implement:

- client-side emergency dispatch
- client-side police calling
- client-side ambulance dispatch
- client-side production LSTM replacement
- autonomous safety decisions
- fake sensor readings
- fake GPS
- fake battery information.

============================================================
MANDATORY AGENTIC SESSION DOCUMENTATION
============================================================

Create:

docs/
└── claude-sessions/
    └── prompt-17-mobile-edge/
        ├── prompt.md
        ├── agent-response.md
        ├── work-done.md
        ├── files-changed.md
        ├── verification.md
        ├── decisions.md
        └── problems-and-solutions.md

prompt.md
------------------------------------------------------------

Store the COMPLETE Prompt 17.

agent-response.md
------------------------------------------------------------

Store the ACTUAL Claude Code agentic session response/output.

Record:

- repository inspection
- mobile architecture
- implementation
- commands
- errors
- fixes
- device testing
- final result

DO NOT fabricate.

work-done.md
------------------------------------------------------------

Record:

IMPLEMENTED

PARTIALLY IMPLEMENTED

NOT IMPLEMENTED

files-changed.md
------------------------------------------------------------

List:

CREATED

MODIFIED

DELETED

files.

verification.md
------------------------------------------------------------

Record actual:

- sensor tests
- GPS tests
- buffering tests
- offline tests
- synchronization tests
- battery tests
- background tests
- reconnect tests
- device tests

decisions.md
------------------------------------------------------------

Document:

Decision
Reason
Alternatives
Why selected

problems-and-solutions.md
------------------------------------------------------------

Record:

Problem
Cause
Solution
Verification

============================================================
UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add:

Prompt 17 — Mobile Edge & Sensor Intelligence

============================================================
1. INSPECT THE EXISTING MOBILE APPLICATION
============================================================

Before implementing:

inspect:

frontend/mobile

React Native configuration

Expo configuration if present

native Android configuration

native iOS configuration

existing GPS code

existing sensor code

permissions

background services

tracking state

telemetry upload

WebSocket

authentication

local storage

offline queue.

Do NOT assume the mobile stack.

Use the EXISTING project architecture.

============================================================
2. DO NOT REWRITE THE MOBILE APP
============================================================

Do not replace the existing mobile application.

Extend it.

Reuse:

existing navigation

authentication

API client

state management

storage

UI system

network layer.

Only introduce dependencies when necessary.

============================================================
3. SENSOR ARCHITECTURE
============================================================

Create clear separation:

LocationService

AccelerometerService

GyroscopeService

TelemetryService

TrackingSessionService

ConnectivityService

BatteryService

SyncService

DeviceHealthService

Do not put all sensor logic into one component.

============================================================
4. TRACKING SESSION
============================================================

Tracking must have an explicit lifecycle:

IDLE

STARTING

ACTIVE

PAUSED

OFFLINE

STOPPING

COMPLETED

ERROR

Do not allow arbitrary state changes.

============================================================
5. START TRACKING
============================================================

When tourist starts tracking:

1. validate permissions
2. create tracking session
3. initialize GPS
4. initialize accelerometer
5. initialize gyroscope
6. initialize local queue
7. initialize connectivity monitoring
8. initialize battery monitoring
9. start telemetry collection
10. synchronize with backend
11. confirm active state.

Do not mark tracking:

ACTIVE

before required initialization succeeds.

============================================================
6. TRACKING SESSION ID
============================================================

Every telemetry record must include:

tracking_session_id.

The ID must originate from the server where possible.

Do not create ambiguous anonymous telemetry.

============================================================
7. DEVICE ID
============================================================

Use a privacy-conscious application-scoped device identifier.

Do NOT collect unnecessary hardware identifiers.

Do not expose:

IMEI

serial number

MAC address

or other unnecessary persistent hardware identifiers.

============================================================
8. GPS COLLECTION
============================================================

Reuse the existing GPS architecture.

GPS records should contain:

timestamp

latitude

longitude

accuracy

altitude where available

speed where available

heading where available

provider/source where available

tracking_session_id

sequence number.

Do not fabricate unavailable fields.

============================================================
9. GPS SAMPLING
============================================================

Sampling frequency should be configurable.

Do not hardcode a frequency throughout the app.

Support:

normal tracking

high-priority tracking

battery-saving tracking

where product requirements justify them.

============================================================
10. GPS ACCURACY
============================================================

Do not treat every coordinate equally.

Record:

accuracy.

Classify:

GOOD

DEGRADED

POOR

UNKNOWN

using configurable thresholds.

Do not silently discard poor GPS.

Mark quality.

============================================================
11. GPS JUMP FILTER
============================================================

Implement basic edge-side validation.

Detect impossible or suspicious jumps using:

timestamp

distance

speed

accuracy.

Do not silently delete the point.

Mark:

GPS_ANOMALY

or:

QUALITY_DEGRADED.

Backend remains authoritative.

============================================================
12. ACCELEROMETER
============================================================

Reuse the existing Prompt 6 sensor implementation.

Record:

timestamp

ax

ay

az

accuracy/availability where supported

sequence

tracking_session_id.

Do not alter the feature ordering used by the production LSTM without creating a new feature version.

============================================================
13. GYROSCOPE
============================================================

Record:

timestamp

gx

gy

gz

accuracy/availability where supported

sequence

tracking_session_id.

Again:

do not change model feature ordering.

============================================================
14. SENSOR TIMESTAMP
============================================================

Use the best available monotonic/time source.

Every sample must have a consistent timestamp representation.

If device sensor timestamps are relative:

convert them carefully to the application's canonical time model.

Document the conversion.

============================================================
15. GPS/IMU SYNCHRONIZATION
============================================================

GPS and IMU operate at different rates.

Do NOT force every sensor to the same sampling frequency.

Create synchronization metadata.

The telemetry pipeline must preserve:

original sensor timestamp

canonical timestamp

sensor type

sequence.

Prompt 16's dataset pipeline remains responsible for final training window alignment.

============================================================
16. SENSOR SEQUENCE NUMBERS
============================================================

Each sensor stream must have monotonic sequence numbers.

Example:

accelerometer:

1001

1002

1003

gyroscope:

5001

5002

5003

Detect:

duplicates

gaps

reordering.

Do not assume global sequence numbers across sensor types.

============================================================
17. LOCAL TELEMETRY QUEUE
============================================================

Implement durable local buffering.

The queue must survive:

component restart

application restart

temporary network failure.

Use the project's existing local storage mechanism if suitable.

Do not keep important telemetry only in:

React state

memory

temporary variables.

============================================================
18. LOCAL QUEUE SCHEMA
============================================================

Each queued batch should contain:

batch_id

tracking_session_id

device_id

created_at

sensor_type

sequence_start

sequence_end

records

attempt_count

last_attempt_at

status.

Do not create millions of individual storage transactions if batching is appropriate.

============================================================
19. BATCHING
============================================================

Telemetry should be uploaded in batches.

Batch size should be configurable.

Consider:

record count

time window

payload size.

Do not create extremely large requests.

============================================================
20. UPLOAD STRATEGY
============================================================

When network is available:

queue

↓

batch

↓

upload

↓

server acknowledgement

↓

mark uploaded

↓

remove/compact local data.

Do not delete local telemetry before server acknowledgement.

============================================================
21. IDEMPOTENCY
============================================================

Every batch must have:

batch_id

and:

idempotency key.

Server must safely handle duplicate uploads.

Do not assume the mobile client can guarantee exactly-once delivery.

Use:

at-least-once delivery

with:

server-side idempotency.

============================================================
22. RETRY
============================================================

Implement:

exponential backoff

jitter

maximum attempts

retry classification.

Do not retry permanent failures forever.

============================================================
23. NETWORK FAILURE
============================================================

When network disappears:

tracking continues if sensors remain available.

Telemetry moves into:

LOCAL_BUFFER.

UI shows:

OFFLINE

or:

SYNC PENDING.

Do not show:

SYNCED.

============================================================
24. RECONNECT
============================================================

When network returns:

1. detect connectivity

2. verify backend availability

3. authenticate if necessary

4. upload pending batches

5. process acknowledgements

6. remove confirmed data

7. resume realtime

8. update sync state.

Do not overload the backend with all historical data at once.

============================================================
25. SYNC PRIORITY
============================================================

Prioritize:

latest operational telemetry

over:

old historical telemetry

where appropriate.

However, do not permanently starve historical batches.

Use fair queueing.

============================================================
26. OFFLINE QUEUE LIMIT
============================================================

Define:

maximum local storage

maximum age

maximum batch count.

When limits are approached:

surface a clear diagnostic.

Do not silently delete safety-relevant telemetry.

If deletion is unavoidable:

record:

DATA_DROPPED

reason

count

time range.

============================================================
27. BATTERY MONITORING
============================================================

Monitor:

battery percentage

charging state

low-power state where available.

Do not require unnecessary high-frequency battery polling.

============================================================
28. BATTERY-AWARE SAMPLING
============================================================

Define configurable policies.

Example:

NORMAL

normal sampling

LOW BATTERY

reduced optional telemetry frequency

CRITICAL BATTERY

preserve essential location/tracking according to product policy.

Do NOT completely disable safety-critical tracking solely because battery is low.

============================================================
29. ADAPTIVE SAMPLING
============================================================

Create a controlled sampling policy.

Inputs may include:

battery

network

movement state

tracking priority

incident state

GPS quality.

Output:

sampling configuration.

Do NOT allow an ML model to dynamically choose arbitrary sensor rates.

Policy must be deterministic and bounded.

============================================================
30. INCIDENT MODE
============================================================

When the tourist has an active incident:

tracking may switch to:

HIGH_PRIORITY

according to explicit configuration.

This may increase:

GPS frequency

telemetry upload frequency

sync priority.

Do not increase IMU frequency beyond device/platform limitations.

============================================================
31. BACKGROUND TRACKING
============================================================

Implement using the actual mobile platform capabilities.

Do not assume JavaScript timers continue reliably in the background.

If React Native:

inspect whether native background services/modules are required.

Android and iOS have different restrictions.

Implement platform-appropriate behavior.

============================================================
32. ANDROID BACKGROUND
============================================================

Inspect current Android configuration.

If foreground service is required:

implement it properly.

Requirements may include:

foreground service declaration

notification

location permission

appropriate service type

lifecycle handling.

Do not bypass Android platform restrictions.

============================================================
33. IOS BACKGROUND
============================================================

Inspect current iOS configuration.

Use appropriate:

location background capability

motion/sensor capabilities where supported

permission declarations

lifecycle behavior.

Do not claim continuous background sensor access if iOS does not guarantee it.

============================================================
34. PERMISSIONS
============================================================

Handle:

location permission

background location where applicable

motion/sensor permission where applicable

notification permission

camera only if existing functionality requires it.

Do not request all permissions at app launch.

Request contextually.

============================================================
35. PERMISSION STATES
============================================================

Support:

NOT_REQUESTED

GRANTED

DENIED

RESTRICTED

LIMITED

BLOCKED

where platform supports.

Provide user guidance when permission is blocked.

============================================================
36. PERMISSION RECOVERY
============================================================

If user denies location:

show:

why location is required

how to enable it.

Do not repeatedly spam permission prompts.

============================================================
37. SENSOR AVAILABILITY
============================================================

Not every device has identical sensors.

Detect:

accelerometer available

gyroscope available

GPS available.

If gyroscope unavailable:

telemetry quality must reflect it.

Do not fabricate gyroscope values.

============================================================
38. DEVICE CAPABILITY PROFILE
============================================================

Create:

DeviceCapabilityProfile

containing:

platform

OS version

app version

sensor availability

GPS support

background capability

battery capability

network capability.

Do not collect unnecessary identifying data.

============================================================
39. DEVICE HEALTH
============================================================

Track:

battery

storage availability

network

GPS

accelerometer

gyroscope

app version

tracking status

sync status.

This becomes visible in diagnostics.

============================================================
40. TELEMETRY HEALTH
============================================================

Display:

samples collected

samples queued

samples uploaded

last upload

queue size

sensor status

GPS status

network status.

Do not show fake health.

============================================================
41. SYNC STATUS
============================================================

States:

SYNCED

SYNCING

PENDING

OFFLINE

ERROR

UNKNOWN.

Use actual backend acknowledgement.

============================================================
42. TELEMETRY BACKPRESSURE
============================================================

If server cannot keep up:

mobile must avoid unbounded memory growth.

Use:

local persistence

bounded queue

batching

backoff.

Do not crash because telemetry accumulates.

============================================================
43. SERVER RATE LIMIT
============================================================

If backend responds:

429

respect:

Retry-After

or equivalent.

Do not immediately retry repeatedly.

============================================================
44. SERVER MAINTENANCE
============================================================

If backend unavailable:

keep collecting where feasible.

Show:

SERVER UNAVAILABLE

and:

PENDING SYNC.

Do not claim successful upload.

============================================================
45. AUTHENTICATION EXPIRATION
============================================================

If JWT expires:

pause upload

refresh token through existing auth mechanism

resume safely.

Do not lose telemetry.

Do not put tokens into telemetry payloads.

============================================================
46. APP RESTART
============================================================

After app restart:

recover:

active tracking session

local queue

sync state

sensor configuration

where platform permits.

Do not create a duplicate tracking session if one already exists.

============================================================
47. TRACKING SESSION RECOVERY
============================================================

If a previous session was active:

query backend.

Determine:

active

completed

expired

unknown.

Do not infer state solely from local storage.

============================================================
48. DEVICE REBOOT
============================================================

Do not assume tracking automatically resumes after device reboot.

If platform supports appropriate background restart:

implement cautiously.

Otherwise:

mark tracking unavailable.

Tell the user clearly.

Do not claim continuous tracking when the OS does not permit it.

============================================================
49. TELEMETRY CLOCK DRIFT
============================================================

Detect:

device clock anomalies

large timestamp jumps

future timestamps

timestamps far behind server.

Record:

CLOCK_SKEW.

Do not silently rewrite timestamps without recording the correction.

============================================================
50. SERVER TIME
============================================================

Where useful:

obtain server timestamp during synchronization.

Estimate clock offset.

Do not use a single network round-trip as perfect clock synchronization.

Use it only as an approximation.

============================================================
51. SENSOR DATA VALIDATION
============================================================

Validate:

finite numbers

reasonable ranges

timestamp

sequence

sensor availability.

Do not assume all platform sensor APIs produce valid data.

============================================================
52. SENSOR RANGE
============================================================

Use physically/platform appropriate ranges where known.

Do not invent universal ranges.

If actual sensor units differ:

normalize according to the platform API.

Document units.

============================================================
53. TELEMETRY PRIVACY
============================================================

Telemetry is sensitive.

Protect:

GPS

movement

sensor data

tracking history.

Do not log raw telemetry into application logs.

Do not send raw telemetry to analytics providers.

============================================================
54. LOCAL STORAGE SECURITY
============================================================

Inspect whether sensitive telemetry needs encryption at rest.

If the existing mobile architecture supports secure storage:

use it for:

tokens

keys

sensitive metadata.

Do not put credentials into ordinary unencrypted storage.

============================================================
55. TELEMETRY LOGGING
============================================================

Development logs may show:

sample counts

queue size

sensor status

sync state.

Do NOT log:

full GPS traces

full accelerometer streams

full gyroscope streams

in normal production logs.

============================================================
56. EDGE PREPROCESSING
============================================================

Only implement lightweight preprocessing on-device.

Examples:

validation

normalization if required for transport

batching

compression if appropriate.

Do NOT move the production LSTM to mobile in this prompt.

Backend remains authoritative.

============================================================
57. TELEMETRY COMPRESSION
============================================================

If payload size is significant:

evaluate compression.

Measure:

CPU cost

battery cost

network savings.

Do not add compression merely because it sounds efficient.

============================================================
58. NETWORK TYPE
============================================================

Track:

Wi-Fi

cellular

offline

unknown

where platform permits.

Use network type only for adaptive sync policy.

Do not infer GPS quality from network type.

============================================================
59. CONNECTIVITY HEALTH
============================================================

Distinguish:

device has network

from:

server reachable.

For example:

NETWORK_CONNECTED

but:

SERVER_UNREACHABLE.

============================================================
60. SERVER HEARTBEAT
============================================================

Use existing realtime connection.

Heartbeat should detect:

connection alive

connection stale

reconnect required.

Do not create a second heartbeat system if one already exists.

============================================================
61. REALTIME TELEMETRY
============================================================

Only transmit the telemetry needed by backend realtime operations.

Do NOT stream every 50 Hz sensor sample over WebSocket unless the architecture explicitly requires it.

Use:

batch ingestion

for high-frequency telemetry.

Realtime channels should carry:

status

events

latest-state information.

============================================================
62. LATEST SENSOR STATE
============================================================

Where useful:

publish latest summarized sensor state.

Examples:

sensor status

sample rate

latest timestamp

quality.

Do not broadcast raw streams to authority dashboards.

============================================================
63. MOBILE SAFETY BOUNDARY
============================================================

Mobile may detect:

sensor failure

GPS loss

network loss

battery issue.

Mobile must NOT independently conclude:

"tourist is in danger."

It may report:

sensor/device condition.

Backend safety orchestration decides safety state.

============================================================
64. LOCAL SOS RESILIENCE
============================================================

SOS must remain the highest-priority mobile action.

If network is unavailable:

show:

SOS QUEUED

and retry.

However:

do not falsely display:

AUTHORITY NOTIFIED

until server acknowledgement exists.

============================================================
65. SOS PRIORITY
============================================================

When SOS is triggered:

prioritize network communication.

Attempt immediate upload.

Pause nonessential background uploads if necessary.

Do not delete queued historical data.

============================================================
66. INCIDENT TELEMETRY PRIORITY
============================================================

When active incident:

prioritize:

latest GPS

critical telemetry windows

incident state synchronization.

Do not starve other required system traffic indefinitely.

============================================================
67. USER TRACKING CONTROL
============================================================

Provide clear controls:

Start tracking

Pause where policy allows

Stop tracking

Tracking status

Sync status.

If tracking cannot be stopped during an active safety policy:

make the reason explicit.

Do not hide controls.

============================================================
68. PRIVACY CENTER
============================================================

Create/update privacy UI showing:

location collection

motion sensor collection

tracking status

data usage

retention summary

permissions.

Do not make privacy controls misleading.

============================================================
69. MOBILE TELEMETRY DIAGNOSTICS
============================================================

Create a diagnostics screen for:

GPS

accelerometer

gyroscope

network

battery

queue

sync

tracking session.

This is primarily:

developer/support/diagnostic functionality.

Do not expose technical noise to normal tourists by default.

============================================================
70. DIAGNOSTIC TEST
============================================================

Provide a safe test mode where authorized development builds can verify:

GPS

accelerometer

gyroscope

network

upload

server acknowledgement.

Do not use fake production telemetry.

============================================================
71. SENSOR TEST MODE
============================================================

If synthetic data is required:

mark clearly:

TEST DATA.

Never allow synthetic telemetry to enter the production ML dataset.

============================================================
72. TELEMETRY ENVIRONMENT TAG
============================================================

Where necessary include:

environment:

PRODUCTION

STAGING

DEVELOPMENT

TEST.

Do not mix datasets across environments.

============================================================
73. MOBILE VERSION COMPATIBILITY
============================================================

Telemetry payload must include:

app_version

telemetry_schema_version.

Backend must reject or safely handle incompatible versions.

Do not silently interpret an unknown schema.

============================================================
74. SCHEMA MIGRATION
============================================================

If telemetry schema changes:

support explicit:

telemetry_schema_version.

Do not change fields without versioning when compatibility could break.

============================================================
75. FEATURE VERSION BOUNDARY
============================================================

The mobile telemetry schema version is NOT the same as:

ML feature version.

Keep separate:

telemetry_schema_version

feature_version

model_version.

============================================================
76. DATA PIPELINE INTEGRATION
============================================================

Verify:

mobile telemetry

↓

backend ingestion

↓

MongoDB

↓

dataset builder

↓

feature pipeline

↓

LSTM inference

works without schema mismatch.

============================================================
77. ANALYTICS INTEGRATION
============================================================

Verify mobile diagnostics metrics feed Prompt 15 where appropriate:

tracking quality

GPS quality

telemetry quality

offline periods

sync latency.

Do not duplicate metrics unnecessarily.

============================================================
78. DEVICE PERFORMANCE
============================================================

Measure:

CPU

memory

battery impact

sensor collection overhead

network usage.

Do not claim battery efficiency without measurement.

============================================================
79. BATTERY TESTING
============================================================

Test at:

100%

50%

20%

10%

where practical.

Verify:

sampling policy

sync behavior

tracking behavior.

Do not claim exact battery consumption without actual device measurement.

============================================================
80. BACKGROUND TESTING
============================================================

On actual supported devices:

start tracking

lock screen

background app

move safely

wait

return to app

verify:

tracking session

GPS

telemetry

queue

sync.

Do not claim background tracking works from simulator-only testing.

============================================================
81. NETWORK TESTING
============================================================

Test:

Wi-Fi

cellular

offline

network switching.

Verify:

no data loss

no duplicate upload

correct sync state.

============================================================
82. APP RESTART TEST
============================================================

Test:

tracking active

kill app

restart

recover state

sync queue.

Document platform limitations.

============================================================
83. SENSOR FAILURE TEST
============================================================

Simulate/disable:

gyroscope

accelerometer

GPS.

Verify:

correct health state

no fabricated values

backend receives quality information.

============================================================
84. SERVER FAILURE TEST
============================================================

Server unavailable:

mobile continues local buffering

reconnect

uploads safely.

Verify:

idempotency

no duplicates.

============================================================
85. LARGE OFFLINE QUEUE TEST
============================================================

Generate realistic offline telemetry.

Verify:

storage remains bounded

batching works

sync resumes

UI remains responsive.

============================================================
86. SECURITY TESTING
============================================================

Verify:

telemetry authorization

device registration ownership

secure token storage

no telemetry secrets in logs

no cross-user telemetry

no raw telemetry in public APIs.

============================================================
87. MOBILE UI
============================================================

Update tourist mobile UI with:

TRACKING STATUS

GPS STATUS

SENSOR STATUS

SYNC STATUS

BATTERY STATUS

ACTIVE SAFETY STATUS

SOS

where appropriate.

The main tourist interface should remain simple.

Do not turn the home screen into a developer dashboard.

============================================================
88. TRACKING STATUS COMPONENT
============================================================

Show concise status:

Tracking Active

GPS Good

Sensors Ready

Synced

or:

Tracking Active

GPS Degraded

Sync Pending

Do not expose meaningless technical numbers by default.

============================================================
89. ACTIVE INCIDENT UI
============================================================

During an incident:

prioritize:

SOS status

authority status

connection

latest location status.

Do not distract the tourist with sensor diagnostics.

============================================================
90. DARK MODE
============================================================

Follow the existing premium B2G/product design language.

Dark mode:

deep neutral

premium

readable

not pure black

not neon.

Critical states should remain immediately distinguishable.

============================================================
91. ACCESSIBILITY
============================================================

Ensure:

large touch targets

screen-reader labels

clear status text

color-independent status

high contrast.

Do not communicate:

GPS unavailable

only through color.

============================================================
92. DOCUMENTATION
============================================================

Create:

docs/mobile-edge-architecture.md

Document:

1. sensor architecture

2. GPS

3. IMU

4. tracking session

5. background tracking

6. permissions

7. local queue

8. batching

9. retries

10. synchronization

11. battery

12. connectivity

13. device health

14. privacy

15. security

16. Android behavior

17. iOS behavior

18. failure handling

19. telemetry schema

20. backend integration

============================================================
93. TELEMETRY CONTRACT
============================================================

Create:

docs/mobile-telemetry-contract.md

Document:

GPS payload

accelerometer payload

gyroscope payload

sequence

timestamp

tracking_session_id

device_id

schema version

batch structure

quality flags

acknowledgement.

============================================================
94. SESSION DOCUMENTATION
============================================================

Before finishing ensure:

docs/claude-sessions/prompt-17-mobile-edge/

contains:

prompt.md
agent-response.md
work-done.md
files-changed.md
verification.md
decisions.md
problems-and-solutions.md

agent-response.md MUST contain the actual agentic session response/output.

Do not fabricate it.

============================================================
95. UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add Prompt 17.

Include:

Prompt number

Title

Objective

Status

Mobile architecture

Device testing

Session documentation path

============================================================
96. VALIDATION
============================================================

Run:

frontend tests

mobile tests

backend integration tests

type-check

lint

sensor tests

GPS tests

telemetry tests

offline queue tests

sync tests

idempotency tests

reconnect tests

permission tests

tracking lifecycle tests

device capability tests.

Verify:

1. GPS collection works

2. accelerometer collection works

3. gyroscope collection works

4. tracking lifecycle works

5. background behavior is correct

6. local buffering works

7. batch upload works

8. retries work

9. idempotency works

10. reconnect works

11. app restart recovery works

12. battery policy works

13. sensor failure handling works

14. clock skew handling works

15. GPS quality works

16. network state works

17. device health works

18. SOS priority works

19. active incident priority works

20. telemetry schema compatibility works

21. privacy controls work

22. no fake sensor data exists in production

23. no raw telemetry leaks into logs

24. no client-side emergency dispatch exists.

============================================================
97. PHYSICAL DEVICE TESTING
============================================================

Where actual supported devices are available:

TEST:

Android device

iOS device

or the actual supported platform.

Test:

GPS

accelerometer

gyroscope

background

screen lock

network switch

offline

reconnect

battery

app restart.

Do NOT claim physical-device success without actual testing.

If a device is unavailable:

write:

PHYSICAL DEVICE VERIFICATION NOT AVAILABLE.

============================================================
98. PERFORMANCE TESTING
============================================================

Measure on actual devices where possible:

CPU usage

memory

battery impact

network data

sensor overhead

queue performance.

Do not invent measurements.

============================================================
99. NO MOCK PRODUCTION DATA
============================================================

Search for:

mockGPS

fakeGPS

fakeAccelerometer

fakeGyroscope

randomTelemetry

demoTelemetry

fakeBattery

fakeSensor

Production paths must use:

real device APIs.

Synthetic data may exist only in:

tests

development

explicit simulator/test mode.

============================================================
100. FINAL ACCEPTANCE CRITERIA
============================================================

Prompt 17 is complete only when:

- mobile sensor architecture exists

- GPS works

- accelerometer works

- gyroscope works

- tracking session lifecycle exists

- background behavior exists where platform supports it

- local telemetry queue exists

- batch upload exists

- idempotency exists

- retry exists

- offline operation exists

- reconnect exists

- app restart recovery exists

- battery monitoring exists

- adaptive sampling exists

- sensor health exists

- GPS quality exists

- connectivity health exists

- device health exists

- clock skew handling exists

- telemetry schema version exists

- backend integration works

- ML pipeline compatibility works

- analytics integration works

- privacy UI exists

- diagnostics exist

- physical testing is documented

- tests pass

- documentation exists

- actual agentic session response is documented.

DO NOT claim:

continuous background execution

full sensor availability

battery efficiency

physical device compatibility

unless actually tested on the relevant platform/device.

============================================================
101. FINAL RESPONSE
============================================================

Return:

MOBILE ARCHITECTURE

GPS

ACCELEROMETER

GYROSCOPE

TRACKING SESSION

BACKGROUND EXECUTION

PERMISSIONS

LOCAL BUFFER

BATCHING

RETRY

OFFLINE

RECONNECT

IDEMPOTENCY

GPS/IMU SYNCHRONIZATION

BATTERY MANAGEMENT

ADAPTIVE SAMPLING

DEVICE HEALTH

SENSOR HEALTH

TELEMETRY HEALTH

CLOCK SYNCHRONIZATION

SOS RESILIENCE

INCIDENT MODE

TELEMETRY CONTRACT

BACKEND INTEGRATION

ML INTEGRATION

ANALYTICS INTEGRATION

ANDROID STATUS

IOS STATUS

PHYSICAL DEVICE TESTS

PERFORMANCE RESULTS

SECURITY RESULTS

TEST RESULTS

TYPE CHECK

LINT

MOCK DATA STATUS

KNOWN LIMITATIONS

FILES CREATED

FILES MODIFIED

SESSION DOCUMENTATION

Do not give a generic completion message.

Report actual implementation and verification results.

If something is not implemented, explicitly say so.

============================================================
PROMPT 17 COMPLETE