# TourSafe Incident Data Governance & Retention Policy

**Scope:** SOS Alerts, Responder Dispatches, Multi-Party Comms, CAD Synchronization, and Legal Holds  

---

## 1. Operational Ownership & Lifecycle States

Emergency incidents progress through a strictly audited lifecycle:
$$\text{REPORTED} \longrightarrow \text{ACKNOWLEDGED} \longrightarrow \text{ASSIGNED} \longrightarrow \text{DISPATCHED} \longrightarrow \text{ON\_SCENE} \longrightarrow \text{RESOLVED} \longrightarrow \text{CLOSED} \longrightarrow \text{ARCHIVED}$$

* **Primary Operational Owner:** Jurisdiction Incident Commander.
* **Access Control:** Restricted to assigned responders, dispatchers within jurisdiction, and verified emergency contacts.

---

## 2. Retention & Legal Holds

* **Statutory Baseline Retention:** 730 days (2 years) from incident closure date.
* **Legal Hold (`LEGAL_HOLD`):** When placed by authorized authority or legal counsel, automatic retention deletion jobs are strictly blocked.
* **Deletion Verification:** No incident under active investigation, active SOS state, or unresolved legal hold can be deleted by standard DSR erasure requests or automated retention sweeps.
