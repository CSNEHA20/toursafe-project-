# Responsive & Multi-Form-Factor Audit Report

## 1. Target Form Factors
TourSafe is engineered for seamless operation across three primary device classes:
1. **Desktop Multi-Monitor Command Displays** (1920x1080, 2560x1440, 4K UHD)
2. **Field Tablet Rugged Devices** (iPad Pro, Samsung Galaxy Tab Active)
3. **Mobile Handsets** (Android & iOS Smartphones, 375px - 430px widths)

---

## 2. Layout Adaptability Matrix

| Screen / Module | Mobile (< 768px) | Tablet (768px - 1024px) | Desktop (> 1024px) |
| :--- | :--- | :--- | :--- |
| **Root Portal Gateway** | Single-column stacked cards with large touch targets | 2-column grid layout with subsystem status bar | 3-column prominent cards with sticky status bar and compliance seals |
| **Authority Command Center** | Tabbed views (Map tab, Alerts tab, Responders tab) | Split screen (Map on top, triage queue below) | High-density 3-pane command layout (Queue left, Map center, AI Copilot right) |
| **Tourist Dashboard** | Single-column safety card stack with fixed bottom SOS | Centered card container with large TSQR preview | Centered responsive column with desktop QR pass print option |
| **Field Responder View** | Full-width incident card with 1-tap action buttons | Dual-pane layout (Dispatch list left, map route right) | Dual-pane wide tactical view with telemetry diagnostics |

---

## 3. Responsive Map Rendering
- **Web**: Leaflet dynamically resizes to fill container width/height on window resize events with auto-recenter on selected incident markers.
- **Mobile**: React Native Maps seamlessly scales vector tile overlays and geofence polygons.
