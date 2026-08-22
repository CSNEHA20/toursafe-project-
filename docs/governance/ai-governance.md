# TourSafe AI & Machine Learning Governance Framework

**Scope:** Real-Time LSTM Anomaly Engine, ML Dataset Lifecycle, and Authority AI Copilot  
**Policy Status:** Active / Audited  

---

## 1. Principles of AI & ML Governance

1. **Human-in-the-Loop Decision Support:** AI and ML models in TourSafe provide decision support only. Automated systems do not execute final irreversible coercive actions without human dispatcher or commander approval.
2. **Explainability & Grounding:** Copilot recommendations must cite authoritative SOP documents and real-time operational state. Hallucinations are actively defended against via prompt grounding.
3. **Data Minimization:** No raw tourist PII, biometric data, or unneeded location histories are submitted to external LLM providers.
4. **Model Safety & Rollback:** Production models require formal evaluation metrics (Precision, Recall, ROC-AUC) and can be rolled back atomically via the Model Registry.

---

## 2. LSTM Anomaly Inference Controls

* **Model Type:** LSTM Autoencoder trained on normalized temporal accelerometer/gyroscope windows.
* **Inference Output:** Reconstruction error anomaly score $[0.0, 1.0]$.
* **Hysteresis & False Positives:** Sustained window confirmation ($N=3$ consecutive anomaly frames) is required before transitioning from `NORMAL` to `POTENTIAL_ANOMALY`.
* **Deterministic Fallback:** Hard kinematic threshold rules (e.g. $>4g$ impact deceleration followed by zero mobility) operate independently of LSTM model weights to guarantee safety even in case of model degradation.

---

## 3. Authority AI Copilot Governance

* **Permitted Use Cases:** SOP knowledge retrieval, incident situation summarization, tactical recommendation drafting, structured tool invocations.
* **Prohibited Use Cases:** Fully automated dispatch without operator review, direct modification of tourist legal status, generation of unverified enforcement orders.
* **Cryptographic Action Previews:** Sensitive tool executions generate a 5-minute cryptographic preview token requiring explicit operator confirmation before execution.
* **Prompt Injection Defense:** Regex filtering and adversarial marker stripping prevent jailbreaking or cross-context prompt exfiltration.
