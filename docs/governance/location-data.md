# TourSafe Location Data Privacy & Governance

**Scope:** GPS Tracking, Live Geolocation, Spatial Analytics & Heatmaps  

---

## 1. Location Precision & Minimization Hierarchy

TourSafe enforces granular location minimization depending on operational context:

1. **EMERGENCY / SOS (Exact Precision):** 6 decimal places ($\approx 0.11\text{ m}$). Applied only during active SOS alarms or assigned responder dispatch missions.
2. **OPERATIONAL SAFETY (High Precision):** 4 decimal places ($\approx 11\text{ m}$). Applied during active tourist tracking sessions for geofence boundary checks.
3. **ANALYTICS & HEATMAPS (Aggregated / Truncated):** 2 decimal places ($\approx 1.1\text{ km}$). Used for B2G corridor analysis, tourist density grids, and executive dashboards.
4. **CITY / REGION LEVEL:** 1 decimal place ($\approx 11\text{ km}$). Used for high-level regional demand forecasting.

---

## 2. Location Access Governance

| Role | Permitted Location Scope | Conditions |
|---|---|---|
| **Tourist (Self)** | Own current & historical GPS trail | Full access via Tourist App |
| **Field Responder** | Assigned incident victim's live location | Only within 500m proximity verification or active mission dispatch |
| **Authority Dispatcher** | Live locations of tourists within own Jurisdiction boundary | Restricted to active tracking sessions; jurisdictional boundary strictly enforced |
| **Executive / Analytics** | Anonymized / 2-decimal truncated heatmaps | No drill-down to individual tourist identity |

---

## 3. Retention & Deletion

* **Live Tracking State:** Stored in Redis ephemeral memory with a 120-second TTL.
* **Trail History:** Retained in MongoDB for 90 days under the standard baseline retention policy.
* **Incident Association:** If a location point is associated with an active emergency incident, it is preserved for 730 days or the duration of an active Legal Hold.
