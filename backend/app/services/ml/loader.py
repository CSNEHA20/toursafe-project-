"""
TourSafe Model Loader & Artifact Registry.
Loads, validates, and caches trained LSTM autoencoder weights, ONNX computational graphs,
robust scalers, calibrated threshold configurations, and metadata manifests.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import onnxruntime as ort
import torch

from ...core.config import settings
from ...ml.config import FEATURE_NAMES, RAW_IMU_CHANNELS
from ...ml.models.lstm_autoencoder import TourSafeLSTMAutoencoder
from ...ml.preprocessing.scaler import TourSafeRobustScaler
from ...schemas.ml import ModelHealthState, ModelMetadata

logger = logging.getLogger("toursafe.ml.loader")


class ModelArtifactLoader:
    """
    Singleton manager for loading, validating, and caching ML inference artifacts.
    """

    def __init__(self):
        self.health_state: ModelHealthState = ModelHealthState.MODEL_LOADING
        self.metadata: Optional[ModelMetadata] = None
        self.raw_metadata: Dict[str, Any] = {}
        self.pytorch_model: Optional[TourSafeLSTMAutoencoder] = None
        self.onnx_session: Optional[ort.InferenceSession] = None
        self.scaler: Optional[TourSafeRobustScaler] = None
        self.threshold_config: Dict[str, Any] = {}
        self.primary_threshold: float = 5.804714
        self.warning_threshold: float = 4.934007
        self.critical_threshold: float = 7.546128
        self.active_runtime: str = "onnx"
        self.device: str = "cpu"
        self.validation_errors: List[str] = []

    def load_and_validate(self, version: Optional[str] = None) -> bool:
        """
        Loads and strictly validates model artifacts for production real-time inference.
        Returns True if loaded and valid, False otherwise without raising fatal exceptions.
        """
        self.health_state = ModelHealthState.MODEL_LOADING
        self.validation_errors.clear()
        target_version = version or settings.ml_model_version

        # Resolve artifact base path
        base_dir = Path(settings.ml_artifacts_dir)
        if not base_dir.is_absolute():
            # Resolve relative to project root / backend directory
            app_dir = Path(__file__).resolve().parent.parent.parent
            base_dir = app_dir / "ml" / "artifacts"

        version_dir = base_dir / target_version
        if not version_dir.exists():
            msg = f"Model artifact directory not found for version '{target_version}' at {version_dir}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        metadata_path = version_dir / "metadata.json"
        model_pt_path = version_dir / "model.pt"
        model_onnx_path = version_dir / "model.onnx"
        scaler_json_path = version_dir / "scaler_config.json"
        scaler_joblib_path = version_dir / "scaler.joblib"
        threshold_path = version_dir / "threshold_config.json"

        # 1. Validate Metadata
        if not metadata_path.exists():
            msg = f"Missing metadata.json in artifact bundle {version_dir}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.raw_metadata = json.load(f)

            self.metadata = ModelMetadata(
                model_version=self.raw_metadata.get("model_version", target_version),
                model_name=self.raw_metadata.get("model_name", "TourSafeLSTMAutoencoder"),
                model_type="lstm_autoencoder",
                framework="pytorch_onnx",
                framework_version=torch.__version__,
                input_timesteps=self.raw_metadata.get("architecture", {}).get("sequence_length", 150),
                input_channels=self.raw_metadata.get("architecture", {}).get("input_dim", 8),
                channel_order=self.raw_metadata.get("features", list(FEATURE_NAMES)),
                sampling_rate_hz=50.0,
                window_seconds=3.0,
                window_stride_seconds=1.0,
                normalization_version="robust_iqr_v1",
                training_dataset_version=self.raw_metadata.get("dataset_summary", {}).get("dataset_name", "uci_har_synth_v1"),
                primary_threshold=self.raw_metadata.get("threshold_summary", {}).get("primary_threshold", 5.804714),
                warning_threshold=self.raw_metadata.get("threshold_summary", {}).get("warning_threshold", 4.934007),
                critical_threshold=self.raw_metadata.get("threshold_summary", {}).get("critical_threshold", 7.546128),
                threshold_method=self.raw_metadata.get("threshold_summary", {}).get("method", "percentile_99"),
                created_at=self.raw_metadata.get("created_at", ""),
                status="production_candidate",
            )
        except Exception as e:
            msg = f"Failed to parse metadata.json: {e}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        # 2. Validate Scaler
        try:
            if scaler_json_path.exists():
                self.scaler = TourSafeRobustScaler.load(scaler_json_path)
            elif scaler_joblib_path.exists():
                self.scaler = TourSafeRobustScaler.load(scaler_joblib_path)
            else:
                msg = f"Missing scaler artifact in {version_dir}"
                logger.error(msg)
                self.validation_errors.append(msg)
                self.health_state = ModelHealthState.MODEL_ERROR
                return False

            if not self.scaler.is_fitted or self.scaler.center_ is None or self.scaler.scale_ is None:
                msg = "Loaded scaler is not fitted or has null parameters"
                logger.error(msg)
                self.validation_errors.append(msg)
                self.health_state = ModelHealthState.MODEL_ERROR
                return False
        except Exception as e:
            msg = f"Failed to load scaler: {e}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        # 3. Validate Threshold Config
        try:
            if not threshold_path.exists():
                msg = f"Missing threshold_config.json in {version_dir}"
                logger.error(msg)
                self.validation_errors.append(msg)
                self.health_state = ModelHealthState.MODEL_ERROR
                return False

            with open(threshold_path, "r", encoding="utf-8") as f:
                self.threshold_config = json.load(f)

            self.primary_threshold = float(self.threshold_config.get("primary_threshold", 5.804714))
            self.warning_threshold = float(self.threshold_config.get("warning_threshold", 4.934007))
            self.critical_threshold = float(self.threshold_config.get("critical_threshold", 7.546128))

            if self.primary_threshold <= 0:
                msg = f"Invalid primary threshold value: {self.primary_threshold}"
                logger.error(msg)
                self.validation_errors.append(msg)
                self.health_state = ModelHealthState.MODEL_ERROR
                return False
        except Exception as e:
            msg = f"Failed to load threshold config: {e}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        # 4. Load & Validate Model (ONNX runtime with PyTorch fallback)
        loaded_runtime = False

        if model_onnx_path.exists():
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                self.onnx_session = ort.InferenceSession(
                    str(model_onnx_path),
                    sess_options=opts,
                    providers=["CPUExecutionProvider"],
                )
                self.active_runtime = "onnx"
                loaded_runtime = True
                logger.info(f"Loaded ONNX inference runtime from {model_onnx_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize ONNX runtime, attempting PyTorch fallback: {e}")

        if not loaded_runtime and model_pt_path.exists():
            try:
                checkpoint = torch.load(str(model_pt_path), map_location=self.device)
                from ...ml.config import ModelConfig
                m_cfg = checkpoint.get("model_config", {})
                cfg = ModelConfig(
                    input_dim=m_cfg.get("input_dim", 8),
                    sequence_length=m_cfg.get("sequence_length", 150),
                    hidden_dims=m_cfg.get("hidden_dims", [64, 32]),
                    latent_dim=m_cfg.get("latent_dim", 32),
                    dropout=m_cfg.get("dropout", 0.1),
                    model_name=m_cfg.get("model_name", "TourSafeLSTMAutoencoder"),
                )
                self.pytorch_model = TourSafeLSTMAutoencoder(cfg)
                self.pytorch_model.load_state_dict(checkpoint["model_state_dict"])
                self.pytorch_model.eval()
                self.pytorch_model.to(self.device)
                self.active_runtime = "pytorch"
                loaded_runtime = True
                logger.info(f"Loaded PyTorch inference runtime from {model_pt_path}")
            except Exception as e:
                msg = f"Failed to load PyTorch model: {e}"
                logger.error(msg)
                self.validation_errors.append(msg)
                self.health_state = ModelHealthState.MODEL_ERROR
                return False

        if not loaded_runtime:
            msg = f"Neither ONNX nor PyTorch model could be loaded from {version_dir}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        # 5. Numerical & Shape Compatibility Smoke Test
        try:
            dummy_input = np.zeros((1, 150, 8), dtype=np.float32)
            out = self.infer_raw(dummy_input)
            if out.shape != (1, 150, 8):
                msg = f"Model output shape mismatch. Expected (1, 150, 8), got {out.shape}"
                logger.error(msg)
                self.validation_errors.append(msg)
                self.health_state = ModelHealthState.MODEL_ERROR
                return False
        except Exception as e:
            msg = f"Smoke test inference failed: {e}"
            logger.error(msg)
            self.validation_errors.append(msg)
            self.health_state = ModelHealthState.MODEL_ERROR
            return False

        self.health_state = ModelHealthState.MODEL_READY
        logger.info(
            f"✅ ML Model Artifacts '{self.metadata.model_version}' verified and ready for real-time inference (Runtime: {self.active_runtime}, Threshold: {self.primary_threshold:.4f})"
        )
        return True

    def infer_raw(self, x_input: np.ndarray) -> np.ndarray:
        """
        Executes low-level inference on a normalized (N, 150, 8) or (1, 150, 8) tensor.
        Returns reconstructed (N, 150, 8) array.
        """
        if self.health_state != ModelHealthState.MODEL_READY and self.health_state != ModelHealthState.MODEL_LOADING:
            raise RuntimeError(f"ML Model is not ready for inference (Current state: {self.health_state})")

        x_arr = np.asarray(x_input, dtype=np.float32)
        if x_arr.ndim == 2:
            x_arr = np.expand_dims(x_arr, axis=0)

        if self.active_runtime == "onnx" and self.onnx_session is not None:
            input_name = self.onnx_session.get_inputs()[0].name
            outputs = self.onnx_session.run(None, {input_name: x_arr})
            return outputs[0]
        elif self.pytorch_model is not None:
            with torch.no_grad():
                tensor_in = torch.from_numpy(x_arr).to(self.device)
                recon = self.pytorch_model(tensor_in)
                return recon.cpu().numpy()
        else:
            raise RuntimeError("No active model runtime available.")


model_loader = ModelArtifactLoader()
