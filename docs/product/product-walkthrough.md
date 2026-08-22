# TourSafe Product Walkthrough & Visual Interface Guide

This document provides a guided walkthrough of the core user interfaces and interactive operational modules within TourSafe.

---

## 1. Unified Portal Gateway (`frontend/app/index.tsx`)

The root portal serves as the entry point for all TourSafe stakeholders, automatically detecting active sessions and providing direct access to operational gateways.

- **Active Session Launcher**: If an active session is detected via `useAuthStore`, a 1-click workspace launcher appears at the top banner with the user's role and email.
- **Three Operational Gateways**:
  1. **Authority Command Center**: Dedicated to District Collectors, Police SPs, Tourism Officers, and Central Dispatchers.
  2. **Tourist Safety Companion**: Dedicated to domestic and international tourists exploring registered zones.
  3. **Field Responder Operations**: Dedicated to on-duty police patrol units, mountain rescue, and emergency medical services.
- **Subsystem Status Grid**: Real-time indicators showing the operational readiness of FastAPI Core, Realtime Bus, LSTM Motion AI, and Spatial Geofencing.
- **Compliance Certification**: Verified badges for India DPDP Act 2023, ISO 27001 ISMS, and AES-256 GCM encryption.

---

## 2. Authority Command Center (`frontend/app/admin/(tabs)/dashboard.tsx`)

The Command Center provides a high-density operational command display designed for multi-monitor command environments.

### Core Modules:
- **Situational Awareness Map**:
  - Live clustering of tourists, active field responders, and polygon safety zones.
  - Color-coded hazard perimeters: Green (Safe), Amber (Warning), Red (Danger), Slate (Restricted).
  - Live responder location beacons with heading, speed, and battery status.
- **Real-Time Incident Triage Queue**:
  - Filterable by severity (Critical, High, Medium, Low) and status (Open, Dispatched, In Progress, Resolved).
  - Single-click automated responder dispatch using Haversine proximity calculations.
- **Operational Health & Golden Signals Bar**:
  - Displays live API p95 latency, error rates, and load-shedding states.
- **Authority AI Copilot**:
  - Right-side conversational panel grounded in live database state and SOP documents.
  - Supports natural language inquiries ("Which zones have elevated risk?") and action proposals with cryptographic confirmation tokens.
- **DPDP & ISO 27001 Governance Dashboard**:
  - Real-time framework readiness score (ISO 27001: 94.2%, DPDP: 96.8%).
  - Legal hold management and single-click sanitized compliance evidence export.

---

## 3. Tourist Safety Companion (`frontend/app/tourist/(tabs)/dashboard.tsx`)

The Tourist App is designed for high reliability, minimal cognitive overhead, and battery efficiency.

### Core Features:
- **Emergency SOS Activator**:
  - High-visibility red trigger button with 3-second physical countdown and haptic feedback to prevent accidental triggers.
  - Immediate fallback to SMS/Voice broadcast if IP connectivity is degraded.
- **Digital Tourist Credential (TSQR Pass)**:
  - Ed25519-signed QR pass containing verifiable tourist identity, blood group, emergency contacts, and validity dates.
- **Zone Awareness Radar**:
  - Live detection of current geofence perimeter with audible and visual alerts upon approaching hazard boundaries (e.g. steep cliffs, restricted wildlife zones).
- **DPDP Act 2023 Privacy Center**:
  - User-controlled toggle for location tracking, IMU sensor telemetry, and KYC document retention.
  - Self-service Data Subject Request (DSR) logging and 1-click machine-readable JSON archive export.

---

## 4. Field Responder Operations (`frontend/app/responder/index.tsx`)

The Responder interface gives field units immediate tactical clarity without UI clutter.

### Core Features:
- **Mission Assignment Alert**:
  - High-priority modal with tourist coordinates, distance, estimated travel time, and reported medical/hazard conditions.
- **Status Transition Workflow**:
  - 1-tap state updates: `ACKNOWLEDGED` → `EN_ROUTE` → `ON_SCENE` → `RESOLVED`.
- **Field Assessment & Evidence Logging**:
  - Real-time text and checklist submission to attach directly to the central e-FIR and incident audit log.
- **Offline Resiliency**:
  - Local SQLite queuing for GPS telemetry and status changes when operating in mountain valleys with zero cellular reception, auto-syncing upon reconnection.
