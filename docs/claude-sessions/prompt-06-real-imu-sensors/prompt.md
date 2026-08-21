TOURSAFE — PROMPT 6
REAL IMU SENSOR ACQUISITION
ACCELEROMETER + GYROSCOPE
TIMESTAMP SYNCHRONIZATION
50 HZ IMU PIPELINE
SENSOR QUALITY MONITORING
REAL DEVICE TELEMETRY FOUNDATION

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
- medical information
- emergency contacts
- itinerary
- KYC foundation

PROMPT 3
- real geospatial zone database
- GeoJSON boundaries
- zone CRUD
- zone APIs
- MongoDB geospatial indexes
- zone audit foundation

PROMPT 4
- authenticated realtime communication
- realtime connection manager
- event envelope
- event registry
- frontend realtime client
- realtime event dispatcher
- Redis connection foundation

PROMPT 5
- real GPS acquisition
- foreground tracking
- background tracking where supported
- tracking sessions
- location validation
- Redis latest location
- MongoDB location history
- location.updated realtime event
- authority live location

NOW IMPLEMENT:

REAL ACCELEROMETER + GYROSCOPE SENSOR ACQUISITION.

============================================================
STRICT SCOPE
============================================================

This prompt implements ONLY the mobile IMU acquisition foundation.

DO NOT implement:

- LSTM
- TensorFlow training
- ONNX inference
- anomaly detection
- anomaly scoring
- fall detection
- geo-fencing
- geo-fence entry detection
- geo-fence exit detection
- SOS automation
- automatic emergency alerts
- blockchain
- DID
- IPFS
- e-FIR
- responder routing
- FCM emergency dispatch

Do not create fake AI logic.

Do not create fake anomaly scores.

Do not generate simulated accelerometer values.

Do not generate simulated gyroscope values.

Do not generate fake telemetry.

The production path MUST use the physical device sensors.

============================================================
MANDATORY AGENTIC SESSION DOCUMENTATION
============================================================

Every Claude Code prompt/session MUST be permanently documented.

Create:

docs/
└── claude-sessions/
    └── prompt-06-real-imu-sensors/
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

Store the COMPLETE Prompt 6 text.

Do not summarize it.

------------------------------------------------------------
agent-response.md
------------------------------------------------------------

Store the ACTUAL Claude Code agentic session response/output.

Record meaningful:

- initial analysis
- repository inspection
- commands executed
- files inspected
- implementation actions
- terminal output
- errors
- fixes
- tests
- final response

Do NOT fabricate an agent response.

Do NOT write a retrospective pretending to be the original session.

If output is extremely large, preserve meaningful command/output sections and explicitly mark abbreviated portions.

------------------------------------------------------------
work-done.md
------------------------------------------------------------

Document exactly what was implemented.

Separate:

IMPLEMENTED

PARTIALLY IMPLEMENTED

NOT IMPLEMENTED

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
- type-check
- lint
- sensor integration checks
- realtime checks
- physical device verification
- sampling-frequency measurements
- permission checks

Include commands and actual results.

------------------------------------------------------------
decisions.md
------------------------------------------------------------

For important architecture decisions record:

Decision
Reason
Alternatives
Why selected

------------------------------------------------------------
problems-and-solutions.md
------------------------------------------------------------

Record actual problems encountered.

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

Prompt 6 — Real IMU Sensor Acquisition

Include:

- objective
- status
- major components
- verification
- session folder

============================================================
1. INSPECT THE EXISTING SENSOR IMPLEMENTATION
============================================================

Before modifying anything inspect:

package.json

app.json

app.config.*

lib/

store/

types/

components/

app/tourist/

Search the repository for:

expo-sensors

Accelerometer

Gyroscope

DeviceMotion

Magnetometer

sensor

accelerometer

gyroscope

motion

telemetry

simulation

mockData

fake sensor

random sensor

Also inspect the implementation created by Prompt 5.

Determine how:

device_id

tourist_id

session_id

tracking session

realtime connection

are currently represented.

Do not create duplicate session abstractions unnecessarily.

============================================================
2. EXPO SENSOR CAPABILITIES
============================================================

Use the Expo sensor APIs compatible with the project's installed Expo SDK.

Before implementing:

inspect package.json

determine the installed Expo SDK version

verify which sensor APIs are supported by that SDK.

Do not blindly install incompatible packages.

Use:

expo-sensors

where appropriate.

The production implementation must read actual:

Accelerometer

Gyroscope

sensor data.

============================================================
3. SENSOR SERVICE ARCHITECTURE
============================================================

Create a dedicated IMU service.

Suggested structure:

lib/
└── sensors/
    ├── accelerometer.ts
    ├── gyroscope.ts
    ├── imu.ts
    ├── synchronizer.ts
    ├── quality.ts
    └── types.ts

Adapt to the existing repository architecture if necessary.

Do not put sensor subscriptions directly inside React screens.

The sensor service owns:

subscription

sampling

cleanup

timestamping

normalization

quality measurement

The UI consumes the service/store.

============================================================
4. ACCELEROMETER COLLECTION
============================================================

Implement real accelerometer collection.

Each sample must contain:

x

y

z

timestamp

sequence_number

sensor_type

session_id

tourist_id

device_id

Use the physical device's accelerometer.

DO NOT:

randomize values

interpolate values

smooth fake values

use mockData.ts

use simulation.ts

fall back to generated values.

If the device does not provide an accelerometer:

return an explicit unavailable/error state.

Do not silently substitute fake values.

============================================================
5. GYROSCOPE COLLECTION
============================================================

Implement real gyroscope collection.

Each sample must contain:

x

y

z

timestamp

sequence_number

sensor_type

session_id

tourist_id

device_id

Use the physical device gyroscope.

DO NOT generate fake values.

Handle unavailable sensors explicitly.

============================================================
6. SAMPLING TARGET
============================================================

TourSafe's architecture expects approximately:

50 Hz IMU telemetry.

Target:

20 ms interval

approximately 50 samples/second.

IMPORTANT:

The operating system and Expo sensor API may not guarantee exactly 50 Hz.

Therefore:

DO NOT claim 50 Hz merely because the requested interval is 20 ms.

Measure the actual delivered frequency.

Track:

sample_count

elapsed_time

observed_frequency

average_interval

minimum_interval

maximum_interval

jitter

dropped_samples where detectable

============================================================
7. CONFIGURABLE SAMPLING
============================================================

Do not hardcode the sampling interval in multiple files.

Create a configuration such as:

IMU_SAMPLE_INTERVAL_MS = 20

Make it configurable.

Do not allow arbitrary runtime configuration from untrusted clients.

Keep the default target:

20 ms

Document that this is a target, not a guaranteed hardware delivery rate.

============================================================
8. SENSOR TIMESTAMPS
============================================================

Every sensor sample MUST have a timestamp.

Use a consistent timestamp strategy.

Prefer a monotonic timing source for measuring intervals where the platform makes one available, while retaining a wall-clock timestamp for server synchronization.

Do not calculate sampling frequency from wall-clock timestamps alone if a suitable monotonic timer is available.

Document:

wall-clock timestamp

monotonic interval measurement

and why both may be useful.

============================================================
9. SENSOR SEQUENCE NUMBERS
============================================================

Every sample must have a sequence number.

Sequence numbers must be:

monotonically increasing

associated with a tracking/IMU session

reset only when a new session begins

Do not reuse sequence numbers within a session.

Do not use array indexes as the permanent sequence identifier.

============================================================
10. IMU SESSION
============================================================

Create or extend the tracking session model to support IMU.

The session should contain:

session_id

tourist_id

device_id

started_at

ended_at

status

imu_enabled

accelerometer_enabled

gyroscope_enabled

last_accelerometer_timestamp

last_gyroscope_timestamp

last_sequence_number

observed_frequency

quality_state

Do not create a separate unrelated session system if Prompt 5 already has a reusable tracking session.

Extend it appropriately.

============================================================
11. IMU CONTROLLER
============================================================

Create a unified:

IMUController

or equivalent service.

Responsibilities:

start

stop

pause

resume

subscribe

unsubscribe

collect

normalize

synchronize

measure quality

The controller must prevent duplicate subscriptions.

Calling:

startIMU()

twice

must NOT create two accelerometer subscriptions and two gyroscope subscriptions.

============================================================
12. SENSOR LIFECYCLE
============================================================

Correct lifecycle:

START

↓

verify authentication/session

↓

verify sensor availability

↓

create/activate IMU session

↓

start accelerometer

↓

start gyroscope

↓

receive samples

↓

timestamp

↓

sequence

↓

synchronize

↓

normalize

↓

quality measurement

↓

publish/store according to current architecture

STOP

↓

unsubscribe accelerometer

↓

unsubscribe gyroscope

↓

flush pending state

↓

mark IMU stopped

Do not leave subscriptions running after the session ends.

============================================================
13. SENSOR SYNCHRONIZATION
============================================================

Accelerometer and gyroscope callbacks may not occur at exactly the same timestamp.

DO NOT simply combine:

latestAccelerometer

with:

latestGyroscope

without considering timestamps.

Create a synchronizer.

The synchronizer should:

1. receive accelerometer samples
2. receive gyroscope samples
3. maintain short timestamp-ordered buffers
4. pair samples using timestamp proximity
5. reject or mark excessively mismatched samples
6. produce synchronized IMU records

Define a configurable synchronization tolerance.

Do not invent an arbitrary tolerance without documenting it.

Use a reasonable engineering default and record the decision in:

decisions.md

============================================================
14. CANONICAL IMU SAMPLE
============================================================

Create a canonical:

IMUSample

containing:

sample_id

session_id

tourist_id

device_id

timestamp

sequence_number

accelerometer:

x
y
z

gyroscope:

x
y
z

derived:

acceleration_magnitude

angular_velocity_magnitude

quality:

sensor_timestamp_delta
is_synchronized
quality_state

Do not include AI anomaly fields.

============================================================
15. ACCELERATION MAGNITUDE
============================================================

Calculate:

A_mag = sqrt(
    ax² +
    ay² +
    az²
)

Create a reusable function:

calculateAccelerationMagnitude()

Keep:

ax

ay

az

as raw channels.

Do not replace raw channels with magnitude.

============================================================
16. ANGULAR VELOCITY MAGNITUDE
============================================================

Calculate:

G_mag = sqrt(
    gx² +
    gy² +
    gz²
)

Create:

calculateAngularVelocityMagnitude()

Keep raw:

gx

gy

gz

channels.

Do not replace them with the magnitude.

============================================================
17. SENSOR UNITS
============================================================

Determine the units provided by the installed Expo sensor API.

Do not assume units blindly.

Document:

accelerometer units

gyroscope units

timestamp units

derived magnitude units

The LSTM pipeline later depends on consistent preprocessing.

If the API provides values in a unit different from what the ML pipeline requires, normalize through a clearly documented conversion layer.

Do not silently convert values.

============================================================
18. RAW DATA PRESERVATION
============================================================

Do not destroy raw sensor values.

The system must retain:

ax

ay

az

gx

gy

gz

timestamp

sequence

for downstream processing.

Derived features must be additional fields.

This is important because future model experimentation may require different preprocessing.

============================================================
19. SENSOR QUALITY ENGINE
============================================================

Create a sensor quality module.

Measure:

accelerometer sample frequency

gyroscope sample frequency

synchronized sample frequency

timestamp jitter

sensor mismatch

missing samples where detectable

subscription errors

sensor availability

quality state

Possible states:

excellent

good

degraded

poor

unavailable

Define the thresholds in one configuration module.

Document them.

Do not scatter magic numbers across the codebase.

============================================================
20. ACTUAL FREQUENCY CALCULATION
============================================================

For each sensor calculate:

observed_frequency =
    sample_count / elapsed_time

Also calculate:

average_interval

minimum_interval

maximum_interval

jitter

Do not calculate frequency as:

1 / requested_interval

because that would only represent the target configuration.

============================================================
21. SAMPLE DROP DETECTION
============================================================

Where possible detect missing samples.

If expected interval is approximately:

20 ms

and actual interval becomes significantly larger:

record a gap.

Track:

gap_count

largest_gap

total_gap_duration

Do not claim that every gap is a dropped sample if the OS simply delayed callback delivery.

Use terminology such as:

sample gap

or

delivery gap

when certainty is unavailable.

============================================================
22. LOCAL IMU BUFFER
============================================================

Create a bounded in-memory IMU buffer.

Do NOT keep unlimited sensor history in React state.

The buffer should:

maintain recent samples

have a configurable maximum size

discard old samples when full

preserve sequence ordering

This buffer will later feed:

temporal windows

offline synchronization

AI preprocessing

Do not implement those systems yet.

============================================================
23. STATE MANAGEMENT
============================================================

Extend the existing store architecture.

Expose:

imuStatus

accelerometerStatus

gyroscopeStatus

latestIMUSample

imuFrequency

accelerometerFrequency

gyroscopeFrequency

synchronizationQuality

sampleGapCount

lastIMUTimestamp

imuError

imuSessionId

Actions:

startIMU()

stopIMU()

pauseIMU()

resumeIMU()

resetIMU()

Do not store the entire high-frequency sensor stream in global React state.

Only store:

latest sample

quality metrics

session state

bounded diagnostic information.

============================================================
24. TOURIST SENSOR STATUS
============================================================

Integrate IMU status into the Tourist application.

Do not redesign the UI.

Provide a subtle status indicator where appropriate.

Possible states:

Sensors Ready

Sensors Active

Sensors Degraded

Sensors Unavailable

Do not expose raw 50 Hz telemetry continuously to normal users.

============================================================
25. DEVELOPMENT IMU DIAGNOSTICS
============================================================

Create a development-only IMU diagnostics screen.

Display REAL sensor values:

Accelerometer:

X
Y
Z
Magnitude

Gyroscope:

X
Y
Z
Angular velocity magnitude

Sampling:

Target Hz
Observed Hz
Accelerometer Hz
Gyroscope Hz
Synchronized Hz
Average interval
Jitter
Sample gaps

Session:

Session ID
Sequence number
Tracking status

Sensor:

Accelerometer available
Gyroscope available

Quality:

Overall quality
Synchronization quality

Realtime:

Connection state
Last transmitted sample
Transmission errors

Clearly display:

REAL DEVICE SENSOR DATA

when actual sensors are being read.

If unavailable:

show the actual reason.

Do not fall back to fake values.

============================================================
26. REALTIME TRANSPORT PREPARATION
============================================================

Use the realtime infrastructure from Prompt 4.

Do NOT create a second independent WebSocket implementation.

Create the canonical IMU telemetry message contract.

Example:

{
  "type": "imu.sample",
  "session_id": "...",
  "sequence_number": 123,
  "timestamp": "...",
  "accelerometer": {
    "x": 0,
    "y": 0,
    "z": 0
  },
  "gyroscope": {
    "x": 0,
    "y": 0,
    "z": 0
  },
  "derived": {
    "acceleration_magnitude": 0,
    "angular_velocity_magnitude": 0
  }
}

Do not send fake samples.

Do not yet build the complete server-side telemetry storage pipeline.

That will be Prompt 7.

============================================================
27. HIGH-FREQUENCY TRANSPORT
============================================================

Remember:

50 Hz = approximately 50 samples/sec.

Do NOT send every IMU sample through a UI-oriented Socket.IO event if the architecture established in Prompt 4 uses native WebSocket for high-frequency telemetry.

Use the appropriate high-frequency transport.

Do not broadcast every raw IMU sample to every authority dashboard.

Raw IMU data is for the telemetry/AI pipeline.

Authority clients will later receive derived safety events, not an unrestricted raw 50 Hz stream.

============================================================
28. TELEMETRY AUTHENTICATION
============================================================

Every IMU stream must be authenticated.

The backend must associate the stream with:

authenticated user

tourist_id

device_id

session_id

Do NOT trust arbitrary:

tourist_id

device_id

session_id

from the client without validating them against the authenticated session.

============================================================
29. DEVICE ID
============================================================

Use the device/application installation identifier architecture created earlier.

Do not use:

IMEI

raw hardware identifiers

phone number

email

as the telemetry device identifier.

Persist the application-generated device ID securely.

============================================================
30. SENSOR PERMISSIONS
============================================================

Determine whether the target platforms require explicit motion/sensor permissions.

Implement the appropriate permission/availability handling for:

Android

iOS

Do not assume identical behavior across platforms.

Document platform-specific limitations.

============================================================
31. BACKGROUND SENSOR LIMITATION
============================================================

IMPORTANT:

Do NOT assume accelerometer/gyroscope callbacks will continue indefinitely in the background on both Android and iOS.

Research the actual capabilities of the installed Expo SDK and target platform.

Implement only what is actually supported.

If continuous background IMU collection is not supported by the current Expo architecture:

do NOT fake it.

Document:

SUPPORTED

LIMITED

NOT SUPPORTED

and the native-module path that would be required if future production requirements exceed Expo capabilities.

============================================================
32. POWER CONSUMPTION
============================================================

50 Hz IMU collection can consume battery.

Track and document:

sampling interval

active duration

background behavior

subscription lifecycle

Avoid unnecessary duplicate subscriptions.

Do not implement aggressive battery optimization that changes the required sampling rate without documenting it.

============================================================
33. NO MOCK SENSOR FALLBACK
============================================================

Search for:

mockData.ts

simulation.ts

useMockApi.ts

fake sensor

random accelerometer

random gyroscope

demo telemetry

Ensure production IMU code does NOT depend on them.

Mock sensors may exist for unit tests only.

If test doubles are created:

they must live behind explicit interfaces/adapters.

============================================================
34. BACKEND IMU CONTRACT
============================================================

Create backend schemas for the IMU payload.

Validate:

timestamp

sequence number

session ID

accelerometer values

gyroscope values

derived values

Do not blindly trust client-derived magnitude.

The server may recompute:

acceleration_magnitude

angular_velocity_magnitude

for validation if appropriate.

Document the decision.

Do not persist all high-frequency samples in MongoDB yet.

Prompt 7 will design the telemetry storage/streaming pipeline.

============================================================
35. SERVER ACKNOWLEDGEMENT
============================================================

Define a lightweight acknowledgement strategy.

The client must be able to know whether the server accepted the telemetry stream.

Do not require a full response payload for every 50 Hz sample if that would create unnecessary network overhead.

Design for efficient acknowledgement.

Document the chosen strategy.

============================================================
36. TESTING — PURE FUNCTIONS
============================================================

Create tests for:

1. acceleration magnitude
2. angular velocity magnitude
3. timestamp validation
4. sequence ordering
5. frequency calculation
6. average interval
7. jitter calculation
8. sample gap detection
9. synchronization
10. malformed IMU sample rejection

Use deterministic test data.

============================================================
37. TESTING — SENSOR ADAPTERS
============================================================

Create adapter-level tests.

Test:

sensor available

sensor unavailable

subscription created

subscription stopped

duplicate subscription prevented

cleanup

callback handling

permission/availability failure

Use mocks ONLY at the sensor adapter boundary.

The production implementation must remain real Expo sensor collection.

============================================================
38. TESTING — REAL DEVICE
============================================================

This is mandatory where a physical device is available.

Run the application on a REAL Android device.

Verify:

1. accelerometer permission/availability
2. gyroscope permission/availability
3. real X/Y/Z values
4. values change when device moves
5. values stabilize when device is stationary
6. timestamps are increasing
7. sequence numbers are increasing
8. observed frequency is measured
9. sensor subscriptions stop correctly
10. starting again does not duplicate callbacks
11. accelerometer and gyroscope timestamps can be synchronized
12. diagnostics screen shows real data
13. no mock sensor values are used

If a physical device cannot be tested:

write:

PHYSICAL DEVICE VERIFICATION NOT AVAILABLE

Do not claim physical-device success.

============================================================
39. IMU DIAGNOSTIC EXPORT
============================================================

For development testing, provide a way to capture a bounded diagnostic sample set.

For example:

last 5–10 seconds

or configurable bounded sample count.

Allow developers to inspect:

timestamp

sequence

ax

ay

az

gx

gy

gz

magnitudes

quality

Do NOT build a permanent production data-export feature yet.

This is a development diagnostic.

============================================================
40. IMU ARCHITECTURE DOCUMENTATION
============================================================

Create:

docs/imu-architecture.md

Document:

1. sensor APIs
2. accelerometer
3. gyroscope
4. target sampling frequency
5. actual sampling measurement
6. timestamps
7. sequence numbers
8. synchronization
9. derived magnitudes
10. sensor quality
11. local buffering
12. realtime transport
13. authentication
14. device ID
15. Android limitations
16. iOS limitations
17. background limitations
18. power considerations
19. future telemetry storage
20. future LSTM integration

Explicitly state:

Prompt 6 implements sensor acquisition.

Prompt 6 does NOT implement:

AI

LSTM

anomaly detection

geo-fencing

telemetry persistence architecture

============================================================
41. SESSION DOCUMENTATION
============================================================

Before finishing ensure:

docs/claude-sessions/prompt-06-real-imu-sensors/

contains:

prompt.md
agent-response.md
work-done.md
files-changed.md
verification.md
decisions.md
problems-and-solutions.md

agent-response.md MUST contain the actual Claude Code agentic session response/output.

Do not fabricate it.

============================================================
42. UPDATE SESSION INDEX
============================================================

Update:

docs/claude-sessions/README.md

Add Prompt 6.

Include:

Prompt number

Title

Objective

Status

Major features

Verification

Session documentation path

============================================================
43. VALIDATION
============================================================

Run:

backend tests

frontend tests

type-check

lint

sensor unit tests

synchronization tests

quality tests

realtime contract tests

Then run the application.

Verify:

1. real accelerometer works
2. real gyroscope works
3. target sampling interval is configured
4. actual frequency is measured
5. timestamps are valid
6. sequence numbers are monotonic
7. synchronization works
8. magnitudes are calculated correctly
9. sensor quality is calculated
10. duplicate subscriptions are prevented
11. cleanup works
12. realtime telemetry contract is valid
13. authentication is enforced
14. mock sensor data is not used in production

Fix all discovered issues.

============================================================
44. FINAL ACCEPTANCE CRITERIA
============================================================

Prompt 6 is complete only when:

- real accelerometer acquisition exists
- real gyroscope acquisition exists
- sensor lifecycle exists
- target 50 Hz configuration exists
- actual sampling frequency is measured
- timestamps exist
- sequence numbers exist
- accelerometer/gyroscope synchronization exists
- acceleration magnitude exists
- angular velocity magnitude exists
- quality metrics exist
- bounded local buffer exists
- IMU state management exists
- development diagnostics exist
- authenticated telemetry contract exists
- high-frequency transport preparation exists
- duplicate subscriptions are prevented
- cleanup works
- physical-device verification is performed or explicitly marked unavailable
- tests pass
- type-check passes
- lint passes
- documentation exists
- agentic session response is documented

Do NOT claim:

LSTM implemented

AI implemented

anomaly detection implemented

geo-fencing implemented

telemetry persistence implemented

SOS automation implemented

============================================================
45. FINAL RESPONSE
============================================================

Return:

IMPLEMENTED

FILES CREATED

FILES MODIFIED

SENSOR ARCHITECTURE

ACCELEROMETER IMPLEMENTATION

GYROSCOPE IMPLEMENTATION

SAMPLING CONFIGURATION

ACTUAL OBSERVED FREQUENCY

TIMESTAMP STRATEGY

SYNCHRONIZATION STRATEGY

QUALITY METRICS

REALTIME CONTRACT

AUTHENTICATION

PHYSICAL DEVICE VERIFICATION

TEST RESULTS

TYPE CHECK

LINT

MOCK SENSOR DATA STILL USED

PLATFORM LIMITATIONS

KNOWN LIMITATIONS

SESSION DOCUMENTATION

Do not give a generic completion message.

Report actual verification results.

Implement this prompt now.
