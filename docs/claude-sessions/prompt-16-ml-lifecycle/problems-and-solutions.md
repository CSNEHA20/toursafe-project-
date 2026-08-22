# Problems and Solutions — Prompt 16: ML Data Engineering & Model Lifecycle Platform

## Problem 1: Circular Import in Threshold Calibrator Class Naming
- **Problem**: `ImportError: cannot import name 'MultiTierThresholdCalibrator' from 'app.ml.evaluation.threshold'`.
- **Cause**: The threshold calibration module in Prompt 8 defined the class as `AnomalyThresholdCalibrator` rather than `MultiTierThresholdCalibrator`.
- **Solution**: Refactored `backend/app/ml/lifecycle/training_manager.py` and `backend/tests/test_ml_lifecycle.py` to import and use `AnomalyThresholdCalibrator` and `ThresholdCalibrationResult` directly.
- **Verification**: Verified with `pytest backend/tests/test_ml_lifecycle.py`.

---

## Problem 2: TelemetryWindow Schema Field Mismatch in Unit Tests
- **Problem**: `pydantic_core._pydantic_core.ValidationError: 4 validation errors for TelemetryWindow: window_start, window_end, observed_frequency_hz, completeness_ratio`.
- **Cause**: Unit test instantiated `TelemetryWindow` with `start_timestamp` and `end_timestamp` instead of the canonical contract fields `window_start`, `window_end`, `observed_frequency_hz`, `completeness_ratio`.
- **Solution**: Updated test window fixtures in `backend/tests/test_ml_lifecycle.py` to populate all required canonical fields.
- **Verification**: Tests passed cleanly without validation errors.

---

## Problem 3: Synthetic Generator Fixture Parameter Mismatch
- **Problem**: `TypeError: SyntheticIMUGenerator.generate_cohort() got an unexpected keyword argument 'num_subjects'`.
- **Cause**: Prompt 8's `SyntheticIMUGenerator.generate_cohort` takes `n_train_subjects`, `n_val_subjects`, `n_test_subjects` and directly returns partitioned cohorts `(train_trials, val_trials, test_trials)`.
- **Solution**: Updated the test fixture to call `generate_cohort(n_train_subjects=3, n_val_subjects=1, n_test_subjects=2)`.
- **Verification**: Test executed successfully and verified `.npz` bundle persistence and SHA-256 calculation.
