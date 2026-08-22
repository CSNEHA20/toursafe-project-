# TourSafe Field Operations & Responder User Manual

## 1. Operating Procedure for Field Responders

### Step 1: Starting Your Shift
1. Launch the TourSafe Responder Mobile Application.
2. Verify that your battery percentage and GPS fix accuracy are displayed with a green badge (`±<25m`).
3. Toggle your Operational Readiness status to **AVAILABLE**.
4. Activate **Tactical GPS Tracking** so Command Center dispatchers can discover your unit for nearby geofence breaches and manual SOS events.

### Step 2: Receiving & Reviewing Incident Dispatches
1. When dispatched, your device will sound an emergency alert and display the **Active Incident Card**.
2. Tap **Open Incident Command** to inspect:
   - Severity level (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
   - Incident source (`MANUAL_SOS`, `SAFETY_ENGINE`, `AUTHORITY_COMMAND`).
   - Geofence zone and geodesic distance.
   - Anomaly description (e.g. "Deviated from registered trail in High-Risk Gorge").
3. Make an operational decision:
   - **Accept Dispatch**: Acknowledges deployment and prepares transit.
   - **Reject With Reason**: Choose mandatory reason (e.g. `INSUFFICIENT_CAPABILITY` if technical ropes required, `GEOGRAPHIC_BARRIER` if river impassable). Dispatch returns instantly to central pool.

### Step 3: En Route & Navigation
1. Tap **Commence Transit (Start Response)**. Status updates to `RESPONDING`.
2. Tap **Tactical Map** for real-time guidance vector, ETA, and topographical reference.
3. Use **Operational Chat** to coordinate with Authority Command or communicate with the tourist's verified device.

### Step 4: Arriving on Scene & Scene Assessment
1. Upon reaching the location coordinates, tap **Verify Arrival On Scene**.
2. The system verifies your distance is within 100 meters. If GPS reflection occurs in canyons/dense canopy, tap **Confirm On-Scene Override**.
3. Conduct triage and tap **Submit Scene Assessment**:
   - `TOURIST_SAFE`: All clear, tourist ambulatory.
   - `FIRST_AID_RENDERED`: Minor injuries treated on scene.
   - `MEDICAL_ASSISTANCE`: Paramedic / ambulance required.
   - `EVACUATION_REQUIRED`: Helicopter or marine extraction required.
   - `FALSE_ALARM`: Unintentional activation.
   - `POLICE_ASSISTANCE`: Threat or security incident.

### Step 5: Recording Offline Field Notes
1. In low-signal areas, enter observations in **Tactical Field Notes** and tap **Record Field Note**.
2. Notes are saved locally with offline timestamps and GPS fix.
3. Once back in cellular range, open **Field Diagnostics** and verify pending notes sync to zero.

### Step 6: Handover & Resolution
- **Request Handover**: If you must rotate out due to shift fatigue, equipment breakdown, or higher medical triage requirements, tap **Request Handover**, select the reason and requested replacement unit capability.
- **Conclude Incident Response**: When the mission is complete, tap **Resolve / Close**, provide the final resolution summary, and your status is immediately restored to **AVAILABLE**.
