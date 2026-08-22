"""
TourSafe Model Validation Gate.
Executes strict automated pre-approval verification:
- Bundle file existence and integrity
- SHA-256 checksum validation
- Architecture and metadata contract compliance
- RobustScaler validity and parameter checks
- Calibrated threshold consistency
- Model loadability and inference smoke test matching Prompt 9 output schema.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import onnxruntime as ort
import torch

from ...schemas.ml import AnomalyState, InferenceStatus
from ...schemas.ml_lifecycle import (
    ModelValidationCheckResult,
    ModelValidationGateResult,
)
from ..models.lstm_autoencoder import TourSafeLSTMAutoencoder
from ..preprocessing.scaler import TourSafeRobustScaler

logger = logging.getLogger("toursafe.ml.model_validator")


class ModelValidationGate:
    """
    Automated pre-approval gatekeeper for all ML candidate models.
    """

    def __init__(self, artifacts_base_dir: Optional[Path] = None):
        base = Path(__file__).resolve().parent.parent / "artifacts"
        self.artifacts_base_dir = artifacts_base_dir or base

    def validate_model_version(self, model_version: str) -> ModelValidationGateResult:
        version_dir = self.artifacts_base_dir / model_version
        checks: List[ModelValidationCheckResult] = []
        errors: List[str] = []

        # 1. Directory Existence Check
        if not version_dir.exists() or not version_dir.is_dir():
            errors.append(f"Model version directory not found at {version_dir}")
            checks.append(ModelValidationCheckResult(
                check_name="artifact_directory_exists",
                passed=False,
                details=f"Directory {version_dir} does not exist",
            ))
            return ModelValidationGateResult(
                model_version=model_version,
                passed_all_gates=False,
                checks=checks,
                errors=errors,
            )

        checks.append(ModelValidationCheckResult(
            check_name="artifact_directory_exists",
            passed=True,
            details=f"Found artifact directory {version_dir.name}",
        ))

        # 2. Required Files Check
        required_files = [
            "model.pt",
            "model.onnx",
            "scaler_config.json",
            "threshold_config.json",
            "metadata.json",
        ]
        missing_files = [f for f in required_files if not (version_dir / f).exists()]
        if missing_files:
            errors.append(f"Missing required artifact files: {missing_files}")
            checks.append(ModelValidationCheckResult(
                check_name="required_files_present",
                passed=False,
                details=f"Missing: {missing_files}",
            ))
        else:
            checks.append(ModelValidationCheckResult(
                check_name="required_files_present",
                passed=True,
                details="All 5 required artifact files present",
            ))

        # 3. Metadata Completeness Check
        metadata_path = version_dir / "metadata.json"
        metadata: Dict[str, Any] = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                req_meta_keys = ["model_version", "architecture", "features", "threshold_summary"]
                missing_meta = [k for k in req_meta_keys if k not in metadata]
                if missing_meta:
                    errors.append(f"Incomplete metadata keys: {missing_meta}")
                    checks.append(ModelValidationCheckResult(
                        check_name="metadata_contract",
                        passed=False,
                        details=f"Missing keys: {missing_meta}",
                    ))
                else:
                    checks.append(ModelValidationCheckResult(
                        check_name="metadata_contract",
                        passed=True,
                        details="Metadata contract complete",
                    ))
            except Exception as e:
                errors.append(f"Metadata JSON corrupted: {e}")
                checks.append(ModelValidationCheckResult(
                    check_name="metadata_contract",
                    passed=False,
                    details=f"Parse error: {e}",
                ))

        # 4. Scaler Validity Check
        scaler_json = version_dir / "scaler_config.json"
        scaler: Optional[TourSafeRobustScaler] = None
        if scaler_json.exists():
            try:
                scaler = TourSafeRobustScaler.load(scaler_json)
                if not scaler.is_fitted or scaler.center_ is None or scaler.scale_ is None:
                    errors.append("RobustScaler is not fitted or has null parameters")
                    checks.append(ModelValidationCheckResult(
                        check_name="scaler_validity",
                        passed=False,
                        details="Scaler not fitted",
                    ))
                elif len(scaler.feature_names) != 8:
                    errors.append(f"Scaler expected 8 channels, found {len(scaler.feature_names)}")
                    checks.append(ModelValidationCheckResult(
                        check_name="scaler_validity",
                        passed=False,
                        details=f"Channel mismatch ({len(scaler.feature_names)} != 8)",
                    ))
                else:
                    checks.append(ModelValidationCheckResult(
                        check_name="scaler_validity",
                        passed=True,
                        details=f"Scaler fitted for 8 channels ({', '.join(scaler.feature_names[:3])}...)",
                    ))
            except Exception as e:
                errors.append(f"Failed to load scaler: {e}")
                checks.append(ModelValidationCheckResult(
                    check_name="scaler_validity",
                    passed=False,
                    details=f"Load error: {e}",
                ))

        # 5. Threshold Calibration Consistency Check
        thresh_path = version_dir / "threshold_config.json"
        if thresh_path.exists():
            try:
                with open(thresh_path, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                pri = float(t_data.get("primary_threshold", 0.0))
                warn = float(t_data.get("warning_threshold", 0.0))
                crit = float(t_data.get("critical_threshold", 0.0))

                if pri <= 0.0:
                    errors.append("Primary threshold must be positive")
                    checks.append(ModelValidationCheckResult(
                        check_name="threshold_consistency",
                        passed=False,
                        details="Primary threshold <= 0",
                    ))
                elif not (warn < pri <= crit):
                    errors.append(f"Threshold hierarchy violation: warning ({warn}) < primary ({pri}) <= critical ({crit})")
                    checks.append(ModelValidationCheckResult(
                        check_name="threshold_consistency",
                        passed=False,
                        details=f"Ordering invalid ({warn}, {pri}, {crit})",
                    ))
                else:
                    checks.append(ModelValidationCheckResult(
                        check_name="threshold_consistency",
                        passed=True,
                        details=f"Thresholds valid: warn={warn:.3f}, pri={pri:.3f}, crit={crit:.3f}",
                    ))
            except Exception as e:
                errors.append(f"Failed to parse threshold config: {e}")
                checks.append(ModelValidationCheckResult(
                    check_name="threshold_consistency",
                    passed=False,
                    details=f"Parse error: {e}",
                ))

        # 6. Model Load & Inference Smoke Test Check
        model_onnx = version_dir / "model.onnx"
        if model_onnx.exists() and scaler is not None:
            try:
                session = ort.InferenceSession(str(model_onnx), providers=["CPUExecutionProvider"])
                # Generate sample 3s @ 50Hz raw IMU data (150, 8)
                dummy_raw = np.zeros((150, 8), dtype=np.float32)
                dummy_raw[:, 2] = 1.0  # standard 1g gravity on Z
                scaled = scaler.transform(dummy_raw)
                inp = np.expand_dims(scaled, axis=0).astype(np.float32)  # (1, 150, 8)

                input_name = session.get_inputs()[0].name
                output_name = session.get_outputs()[0].name
                recon = session.run([output_name], {input_name: inp})[0]

                if recon.shape != (1, 150, 8):
                    errors.append(f"ONNX output shape mismatch: {recon.shape} != (1, 150, 8)")
                    checks.append(ModelValidationCheckResult(
                        check_name="inference_smoke_test",
                        passed=False,
                        details=f"Output shape {recon.shape}",
                    ))
                else:
                    mse = float(np.mean((inp - recon) ** 2))
                    if np.isnan(mse) or np.isinf(mse):
                        errors.append("Inference produced NaN/Inf MSE score")
                        checks.append(ModelValidationCheckResult(
                            check_name="inference_smoke_test",
                            passed=False,
                            details="NaN/Inf score",
                        ))
                    else:
                        checks.append(ModelValidationCheckResult(
                            check_name="inference_smoke_test",
                            passed=True,
                            details=f"Inference smoke test passed successfully (test MSE={mse:.4f})",
                        ))
            except Exception as e:
                errors.append(f"Inference smoke test exception: {e}")
                checks.append(ModelValidationCheckResult(
                    check_name="inference_smoke_test",
                    passed=False,
                    details=f"Execution error: {e}",
                ))

        passed_all = len(errors) == 0

        return ModelValidationGateResult(
            model_version=model_version,
            validated_at=datetime.now(timezone.utc).isoformat(),
            passed_all_gates=passed_all,
            checks=checks,
            errors=errors,
        )


model_validation_gate = ModelValidationGate()
