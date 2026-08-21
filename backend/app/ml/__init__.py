"""
TourSafe Machine Learning Package.
Provides deep LSTM Autoencoder anomaly detection, robust IMU preprocessing,
temporal window generation, and versioned artifact management.
"""

from .config import PipelineConfig, default_pipeline_config
from .preprocessing import IMUResampler, FeatureExtractor, TourSafeRobustScaler
from .models import LSTMEncoder, LSTMDecoder, TourSafeLSTMAutoencoder
from .training import AutoencoderTrainer, TrainingResult
from .evaluation import AnomalyThresholdCalibrator, ModelEvaluator, ThresholdCalibrationResult, AnomalyEvaluationReport
from .artifacts import ModelArtifactManager

__all__ = [
    "PipelineConfig",
    "default_pipeline_config",
    "IMUResampler",
    "FeatureExtractor",
    "TourSafeRobustScaler",
    "LSTMEncoder",
    "LSTMDecoder",
    "TourSafeLSTMAutoencoder",
    "AutoencoderTrainer",
    "TrainingResult",
    "AnomalyThresholdCalibrator",
    "ModelEvaluator",
    "ThresholdCalibrationResult",
    "AnomalyEvaluationReport",
    "ModelArtifactManager",
]
