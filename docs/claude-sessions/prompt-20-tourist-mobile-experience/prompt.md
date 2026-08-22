# Prompt 20: Tourist Mobile Experience & Safety Journey

## Goal & Scope
Build the production-oriented client-side TourSafe mobile experience. The tourist moves seamlessly through:
`DOWNLOAD / OPEN APP` → `ONBOARDING` → `ACCOUNT` → `IDENTITY` → `KYC` → `DIGITAL CREDENTIAL` → `TRIP` → `ITINERARY` → `SAFETY SETUP` → `LIVE TRACKING` → `LIVE SAFETY STATUS` → `ZONE AWARENESS` → `ANOMALY / SAFETY EVENTS` → `SOS` → `INCIDENT` → `AUTHORITY / RESPONDER COMMUNICATION` → `TRIP COMPLETION`.

## Core Philosophy
- The tourist application is a **SAFETY COMPANION**, not a surveillance dashboard.
- The tourist must always understand:
  - WHAT is being collected
  - WHY it is being collected
  - WHETHER tracking is active
  - WHETHER data is synced
  - WHETHER an incident exists
  - WHAT action they can take
- The frontend must never independently decide safety status; it displays backend authoritative state and initiates user actions.
- Human-centric, actionable language without intimidating ML error metrics or surveillance jargon.
- Offline resilience with bounded FIFO buffering and reconnection burst synchronization.
