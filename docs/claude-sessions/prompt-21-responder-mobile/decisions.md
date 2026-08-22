# Architectural & Design Decisions — Prompt 21: Responder Mobile Application

## 1. Backend Authoritative State Machine vs Client Autonomy
- **Decision**: The central backend remains strictly authoritative for incident state, responder availability, eligibility, and permission controls.
- **Rationale**: Field responders must operate under verifiable coordination to prevent duplicate dispatches, abandoned incidents, or unauthorized state modifications.

## 2. Privacy Minimization for Field Responders
- **Decision**: Tourist identity profile is strictly minimized to emergency triage fields (name, observed distress category, location coordinates, staleness). Responders do NOT receive raw KYC document numbers, biometric data, or entire contact rosters.
- **Rationale**: Protects tourist privacy while providing adequate context for emergency resolution.

## 3. Idempotent Offline Field Notes Synchronization
- **Decision**: Client assigns each field note a unique `client_note_id` upon creation. Batch sync requests check for existing `client_note_id` records in the incident's note list.
- **Rationale**: In intermittent field network conditions, repeated synchronization requests will not duplicate entries in the authoritative timeline.

## 4. Arrival Verification with Auditable Override
- **Decision**: Proximity is checked using geodesic Haversine distance with a threshold of 100 meters. If GPS reflection occurs (such as in steep mountain valleys or marine areas), responders can activate an auditable manual override.
- **Rationale**: Prevents accidental false arrivals while ensuring field teams are never locked out of logging critical operations when GPS signals degrade.
