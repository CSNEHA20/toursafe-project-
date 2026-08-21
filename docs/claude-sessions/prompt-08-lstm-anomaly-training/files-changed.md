# TourSafe Prompt 8: Files Changed & Created

## 1. Backend Core Configuration
- `backend/app/core/config.py`: Added ML pipeline configuration settings (`ml_model_version`, `ml_artifacts_dir`, `ml_window_samples`, `ml_feature_count`).

## 2. Machine Learning Package (`backend/app/ml/`)

### Configuration & Base Package
- `backend/app/ml/__init__.py`: Package initialization exposing all ML classes and utilities.
- `backend/app/ml/config.py`: Canonical feature channel definitions (8 channels), `WindowConfig`, `ModelConfig`, `TrainingConfig`, `ArtifactConfig`, and `PipelineConfig`.

### Preprocessing (`backend/app/ml/preprocessing/`)
- `backend/app/ml/preprocessing/__init__.py`: Preprocessing exports.
- `backend/app/ml/preprocessing/resampler.py`: `IMUResampler` for uniform 50 Hz linear interpolation with timestamp jitter handling and max gap enforcement ($\le 250\text{ ms}$).
- `backend/app/ml/preprocessing/feature_extractor.py`: `FeatureExtractor` extracting 6 raw IMU channels (`ax, ay, az, gx, gy, gz`) and computing vector magnitudes (`accel_mag, gyro_mag`).
- `backend/app/ml/preprocessing/scaler.py`: `TourSafeRobustScaler` implementing outlier-resistant median and IQR normalization with JSON and Joblib serialization.

### Datasets (`backend/app/ml/dataset/`)
- `backend/app/ml/dataset/__init__.py`: Dataset package exports.
- `backend/app/ml/dataset/synthetic_generator.py`: `SyntheticIMUGenerator` generating high-fidelity multi-subject normal locomotion (walking, jogging, standing, sitting, stairs, transit) and anomalous dynamics (forward/backward/lateral falls, collapses, violent shaking, vehicle impacts).
- `backend/app/ml/dataset/benchmark_loaders.py`: `BenchmarkDatasetAdapter` providing parsers for MobiAct and SisFall open benchmark datasets.
- `backend/app/ml/dataset/dataset_builder.py`: `DatasetBuilder` performing temporal 3-second window extraction and strict subject-wise partitioning (Train Normal: 70%, Val Normal: 15%, Test Normal+Abnormal: 15%) with anti-leakage invariants.

### Models (`backend/app/ml/models/`)
- `backend/app/ml/models/__init__.py`: Model package exports.
- `backend/app/ml/models/lstm_autoencoder.py`: `LSTMEncoder`, `LSTMDecoder`, and `TourSafeLSTMAutoencoder` with PyTorch forward pass, reconstruction error scoring, and ONNX graph export.
- `backend/app/ml/models/baselines.py`: `KinematicPeakDetector`, `IsolationForestDetector`, and `PCAReconstructionDetector` benchmark baseline models.

### Training (`backend/app/ml/training/`)
- `backend/app/ml/training/__init__.py`: Training package exports.
- `backend/app/ml/training/trainer.py`: `AutoencoderTrainer` and `TrainingResult` implementing PyTorch training loop with Adam optimizer, ReduceLROnPlateau scheduling, early stopping, and gradient clipping.

### Evaluation & Thresholding (`backend/app/ml/evaluation/`)
- `backend/app/ml/evaluation/__init__.py`: Evaluation package exports.
- `backend/app/ml/evaluation/threshold.py`: `AnomalyThresholdCalibrator` and `ThresholdCalibrationResult` supporting Percentile (P95/P99), Gaussian ($\mu + 3\sigma$), and IQR threshold calibration.
- `backend/app/ml/evaluation/evaluator.py`: `ModelEvaluator` and `AnomalyEvaluationReport` computing ROC-AUC, PR-AUC, F1, precision, recall, confusion matrix, activity-wise error breakdown, and baseline comparisons.

### Artifacts & Orchestration (`backend/app/ml/artifacts/`, `backend/app/ml/pipeline.py`)
- `backend/app/ml/artifacts/__init__.py`: Artifact package exports.
- `backend/app/ml/artifacts/manager.py`: `ModelArtifactManager` handling versioned artifact bundle serialization (`model.pt`, `model.onnx`, `scaler.joblib`, `scaler_config.json`, `threshold_config.json`, `metadata.json`), ONNX numerical parity verification, and experiment logging (`experiments.jsonl`).
- `backend/app/ml/pipeline.py`: `MLTrainingPipeline` end-to-end runnable CLI and programmatic training orchestrator.

## 3. Test Suite
- `backend/tests/test_ml_pipeline.py`: Comprehensive test suite verifying resampling, feature extraction, robust scaler, anti-leakage splitting, LSTM autoencoder architecture, threshold calibration, and ONNX parity.

## 4. Documentation
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/prompt.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/dataset-research.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/decisions.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/problems-and-solutions.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/files-changed.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/work-done.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/verification.md`
- `docs/claude-sessions/prompt-08-lstm-anomaly-training/agent-response.md`
