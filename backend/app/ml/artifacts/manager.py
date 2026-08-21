"""
TourSafe Model Artifact & Versioning Manager.
Handles atomic persistence, ONNX graph export and parity verification,
scaler/threshold serialization, metadata tracking, and artifact registry.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import onnxruntime as ort
import torch

from ..config import ArtifactConfig, ModelConfig, PipelineConfig
from ..evaluation.evaluator import AnomalyEvaluationReport
from ..evaluation.threshold import ThresholdCalibrationResult
from ..models.lstm_autoencoder import TourSafeLSTMAutoencoder
from ..preprocessing.scaler import TourSafeRobustScaler
from ..training.trainer import TrainingResult


class ModelArtifactManager:
    """
    Manages structured serialization and loading of versioned ML artifacts:
    - PyTorch weights (model.pt)
    - ONNX computational graph (model.onnx)
    - Preprocessing Scaler (scaler.joblib & scaler_config.json)
    - Threshold configuration (threshold_config.json)
    - Metadata and experiment tracking (metadata.json & experiments.jsonl)
    """

    def __init__(self, config: Optional[ArtifactConfig] = None):
        self.config = config or ArtifactConfig()

    def verify_onnx_parity(
        self,
        pytorch_model: TourSafeLSTMAutoencoder,
        onnx_path: Union[str, Path],
        tolerance: float = 1e-4,
    ) -> Tuple[bool, float]:
        """
        Validates numerical parity between PyTorch model and exported ONNX graph.
        """
        pytorch_model.eval()
        onnx_p = str(onnx_path)

        # Test batch (2, 150, 8)
        dummy = np.random.randn(2, pytorch_model.config.sequence_length, pytorch_model.config.input_dim).astype(np.float32)
        dummy_tensor = torch.from_numpy(dummy)

        with torch.no_grad():
            pt_out = pytorch_model(dummy_tensor).cpu().numpy()

        ort_session = ort.InferenceSession(onnx_p, providers=["CPUExecutionProvider"])
        ort_inputs = {ort_session.get_inputs()[0].name: dummy}
        ort_out = ort_session.run(None, ort_inputs)[0]

        max_diff = float(np.max(np.abs(pt_out - ort_out)))
        is_parity_ok = bool(max_diff < tolerance)

        return is_parity_ok, max_diff

    def save_artifact_bundle(
        self,
        model: TourSafeLSTMAutoencoder,
        scaler: TourSafeRobustScaler,
        threshold_result: ThresholdCalibrationResult,
        eval_report: Optional[AnomalyEvaluationReport] = None,
        training_result: Optional[TrainingResult] = None,
        dataset_summary: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Saves all versioned artifacts into the version directory.
        """
        ver = version or self.config.version
        target_dir = self.config.base_dir / ver
        target_dir.mkdir(parents=True, exist_ok=True)

        model_pt_path = target_dir / "model.pt"
        model_onnx_path = target_dir / "model.onnx"
        scaler_joblib_path = target_dir / "scaler.joblib"
        scaler_json_path = target_dir / "scaler_config.json"
        threshold_path = target_dir / "threshold_config.json"
        metadata_path = target_dir / "metadata.json"

        # 1. Save PyTorch State Dict & Architecture Config
        torch.save(
            {
                "version": ver,
                "model_state_dict": model.state_dict(),
                "model_config": {
                    "input_dim": model.config.input_dim,
                    "sequence_length": model.config.sequence_length,
                    "hidden_dims": model.config.hidden_dims,
                    "latent_dim": model.config.latent_dim,
                    "dropout": model.config.dropout,
                    "model_name": model.config.model_name,
                },
            },
            model_pt_path,
        )

        # 2. Export and verify ONNX model
        model.export_onnx(model_onnx_path)
        parity_ok, max_diff = self.verify_onnx_parity(model, model_onnx_path)

        # 3. Save Scaler (both joblib binary and JSON params)
        scaler.save(scaler_joblib_path, scaler_json_path)

        # 4. Save Threshold Configuration
        threshold_result.save(threshold_path)

        # 5. Build Comprehensive Metadata Manifest
        metadata = {
            "model_version": ver,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_name": model.config.model_name,
            "architecture": {
                "input_dim": model.config.input_dim,
                "sequence_length": model.config.sequence_length,
                "hidden_dims": model.config.hidden_dims,
                "latent_dim": model.config.latent_dim,
                "dropout": model.config.dropout,
                "total_parameters": sum(p.numel() for p in model.parameters()),
            },
            "features": scaler.feature_names,
            "onnx_export": {
                "path": str(model_onnx_path.name),
                "parity_verified": parity_ok,
                "max_absolute_difference": round(max_diff, 8),
            },
            "dataset_summary": dataset_summary or {},
            "training_summary": training_result.metrics_summary if training_result else {},
            "threshold_summary": threshold_result.to_dict(),
            "evaluation_report": eval_report.to_dict() if eval_report else {},
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 6. Append to Experiment Tracking log
        self._log_experiment(metadata)

        return metadata

    def _log_experiment(self, metadata: Dict[str, Any]) -> None:
        """Appends experiment summary to experiments.jsonl."""
        self.config.experiments_dir.mkdir(parents=True, exist_ok=True)
        exp_file = self.config.experiments_dir / "experiments.jsonl"
        with open(exp_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(metadata) + "\n")

    def load_artifact_bundle(
        self,
        version: Optional[str] = None,
        device: str = "cpu",
    ) -> Tuple[TourSafeLSTMAutoencoder, TourSafeRobustScaler, ThresholdCalibrationResult, Dict[str, Any]]:
        """
        Loads all versioned artifacts for inference or validation.
        """
        ver = version or self.config.version
        target_dir = self.config.base_dir / ver

        if not target_dir.exists():
            raise FileNotFoundError(f"Artifact directory for version '{ver}' not found at {target_dir}")

        model_pt_path = target_dir / "model.pt"
        scaler_joblib_path = target_dir / "scaler.joblib"
        threshold_path = target_dir / "threshold_config.json"
        metadata_path = target_dir / "metadata.json"

        # Load Metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Load PyTorch Model
        checkpoint = torch.load(model_pt_path, map_location=device)
        m_cfg = checkpoint.get("model_config", {})
        model_config = ModelConfig(
            input_dim=m_cfg.get("input_dim", 8),
            sequence_length=m_cfg.get("sequence_length", 150),
            hidden_dims=m_cfg.get("hidden_dims", [64, 32]),
            latent_dim=m_cfg.get("latent_dim", 16),
            dropout=m_cfg.get("dropout", 0.2),
            model_name=m_cfg.get("model_name", "TourSafeLSTMAutoencoder"),
        )
        model = TourSafeLSTMAutoencoder(model_config)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        model.to(device)

        # Load Scaler
        scaler = TourSafeRobustScaler.load(scaler_joblib_path)

        # Load Thresholds
        threshold_result = ThresholdCalibrationResult.load(threshold_path)

        return model, scaler, threshold_result, metadata
