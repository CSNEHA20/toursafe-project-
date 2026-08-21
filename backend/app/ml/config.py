"""
TourSafe ML Configuration & Hyperparameters.
Defines canonical sensor channels, temporal window dimensions, resampling parameters,
model architecture, training hyperparameters, and artifact persistence configurations.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# Primary and derived IMU feature channel names
FEATURE_NAMES: List[str] = [
    "accel_x",   # g (9.80665 m/s^2)
    "accel_y",   # g
    "accel_z",   # g
    "gyro_x",    # rad/s
    "gyro_y",    # rad/s
    "gyro_z",    # rad/s
    "accel_mag", # g (derived vector magnitude)
    "gyro_mag",  # rad/s (derived vector magnitude)
]

RAW_IMU_CHANNELS: List[str] = [
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]


@dataclass
class WindowConfig:
    """Temporal window configuration parameters matching TourSafe's 3-second contract."""
    nominal_frequency_hz: float = 50.0
    duration_seconds: float = 3.0
    stride_seconds: float = 1.0  # 1s stride = 66.7% window overlap for training
    min_completeness_ratio: float = 0.6
    max_time_gap_ms: float = 250.0

    @property
    def window_samples(self) -> int:
        """Expected timesteps per window (e.g. 50.0 * 3.0 = 150)."""
        return int(round(self.nominal_frequency_hz * self.duration_seconds))

    @property
    def stride_samples(self) -> int:
        """Step size in samples between consecutive window starts."""
        return int(round(self.nominal_frequency_hz * self.stride_seconds))


@dataclass
class ModelConfig:
    """LSTM Autoencoder architectural hyperparameters."""
    input_dim: int = 8  # 6 raw IMU channels + 2 derived kinematic magnitudes
    sequence_length: int = 150  # 3 seconds @ 50 Hz
    hidden_dims: List[int] = field(default_factory=lambda: [64, 32])
    latent_dim: int = 32
    dropout: float = 0.1
    bidirectional: bool = False
    model_name: str = "TourSafeLSTMAutoencoder"


@dataclass
class TrainingConfig:
    """Hyperparameters for model training and optimization."""
    batch_size: int = 32
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    epochs: int = 60
    early_stopping_patience: int = 8
    min_delta: float = 1e-5
    lr_reduce_patience: int = 4
    lr_reduce_factor: float = 0.5
    clip_grad_norm: float = 1.0
    random_seed: int = 42
    device: str = "cpu"  # default to cpu for reproducible cross-platform test runs


@dataclass
class ArtifactConfig:
    """Directory structure and versioning for ML artifacts."""
    version: str = "v1.0.0"
    base_dir: Path = Path(__file__).resolve().parent / "artifacts"
    experiments_dir: Path = Path(__file__).resolve().parent / "experiments"

    @property
    def version_dir(self) -> Path:
        return self.base_dir / self.version

    @property
    def model_weights_path(self) -> Path:
        return self.version_dir / "model.pt"

    @property
    def onnx_model_path(self) -> Path:
        return self.version_dir / "model.onnx"

    @property
    def scaler_path(self) -> Path:
        return self.version_dir / "scaler.joblib"

    @property
    def scaler_json_path(self) -> Path:
        return self.version_dir / "scaler_config.json"

    @property
    def threshold_config_path(self) -> Path:
        return self.version_dir / "threshold_config.json"

    @property
    def metadata_path(self) -> Path:
        return self.version_dir / "metadata.json"


@dataclass
class PipelineConfig:
    """Global configuration coordinating all ML components."""
    window: WindowConfig = field(default_factory=WindowConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    artifact: ArtifactConfig = field(default_factory=ArtifactConfig)
    features: List[str] = field(default_factory=lambda: list(FEATURE_NAMES))


default_pipeline_config = PipelineConfig()
