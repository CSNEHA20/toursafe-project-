# TourSafe — Policy Management & Simulation Architecture

## 1. Executive Summary
TourSafe Policy Management allows administrators to configure and simulate:
1. **Emergency Response Policies**: Multi-stage action graphs, SLAs, and automated responder dispatch.
2. **Escalation Policies**: Timeouts, escalation targets, and circular loop detection.
3. **Notification Policies & Fallbacks**: Channel prioritization, retry intervals, and multi-tier fallbacks.
4. **Safety Intelligence & Risk Fusion Parameters**: Domain weights, signal freshness windows, and threshold tuning.

---

## 2. Response & Escalation Policy Architecture

### 2.1 Escalation Stage Graph
Response policies define sequential or timer-driven escalation stages:

$$\text{Stage 1: Field Unit Dispatch} \xrightarrow{\Delta t_1 = 60s} \text{Stage 2: Secondary Redispatch} \xrightarrow{\Delta t_2 = 120s} \text{Stage 3: Supervisor Escalation}$$

### 2.2 Loop Detection Invariant
The policy compiler validates escalation stage graphs using directed acyclic graph (DAG) checks. Any stage that references itself as `next_stage` or points backward to a lower stage index is rejected with an `Escalation Cycle Error`.

---

## 3. Notification Policies & Fallback Chains

Notification policies specify channel priority and automatic fallback upon delivery failure or timeout:

$$\text{Push Notification (FCM / APNs)} \xrightarrow{\text{Failed / Timeout}} \text{High-Priority SMS (Twilio)} \xrightarrow{\text{Failed}} \text{Authority Review Queue}$$

Supported channels: `PUSH`, `SMS`, `EMAIL`, `VOICE`, `IN_APP`.

---

## 4. Safety Intelligence & Risk Fusion Parameters

Administrators configure the weights applied across multi-signal risk fusion:

$$\text{Composite Risk} = w_{\text{motion}} \cdot S_{\text{motion}} + w_{\text{spatial}} \cdot S_{\text{spatial}} + w_{\text{itin}} \cdot S_{\text{itin}} + w_{\text{env}} \cdot S_{\text{env}} + w_{\text{vuln}} \cdot S_{\text{vuln}}$$

- Normalization constraint: $\sum w_i \approx 1.00$.
- Risk threshold hierarchy: $\text{watch} < \text{elevated} < \text{candidate} < \text{incident}$.
- Modifying parameters in the governance console dynamically updates the active rule engine version (e.g. `safety-rules-v1.3.0`).

---

## 5. Dry-Run Simulation Sandboxes

TourSafe provides sandbox endpoints for testing policies prior to approval:
1. **Policy Simulation**: Simulates dispatch triggers, estimated unit requirements, and expected escalation paths given synthetic incident severity and location.
2. **Safety Rule Simulation**: Evaluates proposed candidate weights against baseline parameters, computing score deltas and explainability breakdowns without mutating production state.
