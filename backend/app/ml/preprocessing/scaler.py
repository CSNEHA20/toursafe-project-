"""
TourSafe IMU Robust Scaler.
Applies median and Interquartile Range (IQR) normalization per feature channel
to protect normalization parameters from extreme kinetic outliers during training.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from ..config import FEATURE_NAMES


class TourSafeRobustScaler(BaseEstimator, TransformerMixin):
    """
    Robust channel-wise scaler designed for multi-axial IMU kinematics.
    Fits center (median) and scale (IQR = Q75 - Q25) across time and sample dimensions.
    Protects against division by zero with small epsilon.
    """

    def __init__(
        self,
        feature_names: Optional[List[str]] = None,
        quantile_range: tuple = (25.0, 75.0),
        eps: float = 1e-6,
    ):
        self.feature_names = list(feature_names or FEATURE_NAMES)
        self.quantile_range = quantile_range
        self.eps = float(eps)

        self.center_: Optional[np.ndarray] = None
        self.scale_: Optional[np.ndarray] = None
        self.n_features_in_: int = len(self.feature_names)
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: Optional[Any] = None) -> "TourSafeRobustScaler":
        """
        Fits the scaler on training data.

        Parameters
        ----------
        X : np.ndarray
            Array of shape (N, T, D) or (N, D).
        """
        X_arr = np.asarray(X, dtype=np.float32)

        # Flatten (N, T, D) to (N * T, D) if 3D
        if X_arr.ndim == 3:
            N, T, D = X_arr.shape
            X_flat = X_arr.reshape(-1, D)
        elif X_arr.ndim == 2:
            X_flat = X_arr
        else:
            raise ValueError(f"Expected 2D or 3D input array, got shape {X_arr.shape}")

        self.n_features_in_ = X_flat.shape[-1]

        # Compute median per channel
        self.center_ = np.median(X_flat, axis=0)

        # Compute IQR per channel
        q_min, q_max = self.quantile_range
        q75 = np.percentile(X_flat, q_max, axis=0)
        q25 = np.percentile(X_flat, q_min, axis=0)
        iqr = q75 - q25

        # Avoid zero division or extreme noise inflation on static channels
        stds = np.std(X_flat, axis=0)
        safe_scale = np.where(iqr > 0.1, iqr, np.where(stds > 0.1, stds, 1.0))
        self.scale_ = safe_scale
        self.is_fitted = True

        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Applies robust standardization (X - center) / scale.
        """
        if not self.is_fitted or self.center_ is None or self.scale_ is None:
            raise RuntimeError("Scaler is not fitted yet. Call fit() before transform().")

        X_arr = np.asarray(X, dtype=np.float32)
        orig_shape = X_arr.shape

        if X_arr.ndim == 3:
            N, T, D = orig_shape
            X_flat = X_arr.reshape(-1, D)
            scaled_flat = (X_flat - self.center_) / self.scale_
            return scaled_flat.reshape(N, T, D).astype(np.float32)
        elif X_arr.ndim == 2:
            return ((X_arr - self.center_) / self.scale_).astype(np.float32)
        else:
            raise ValueError(f"Expected 2D or 3D array, got shape {orig_shape}")

    def fit_transform(self, X: np.ndarray, y: Optional[Any] = None) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """
        Reverses scaling: (X * scale) + center.
        """
        if not self.is_fitted or self.center_ is None or self.scale_ is None:
            raise RuntimeError("Scaler is not fitted yet.")

        X_arr = np.asarray(X, dtype=np.float32)
        orig_shape = X_arr.shape

        if X_arr.ndim == 3:
            N, T, D = orig_shape
            X_flat = X_arr.reshape(-1, D)
            inv_flat = (X_flat * self.scale_) + self.center_
            return inv_flat.reshape(N, T, D).astype(np.float32)
        elif X_arr.ndim == 2:
            return ((X_arr * self.scale_) + self.center_).astype(np.float32)
        else:
            raise ValueError(f"Expected 2D or 3D array, got shape {orig_shape}")

    def to_dict(self) -> Dict[str, Any]:
        """Exports scaler parameters as a JSON-serializable dictionary."""
        if not self.is_fitted or self.center_ is None or self.scale_ is None:
            raise RuntimeError("Cannot serialize unfitted scaler.")

        return {
            "scaler_type": "TourSafeRobustScaler",
            "feature_names": self.feature_names,
            "quantile_range": list(self.quantile_range),
            "eps": self.eps,
            "center": self.center_.tolist(),
            "scale": self.scale_.tolist(),
            "n_features_in": self.n_features_in_,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TourSafeRobustScaler":
        """Instantiates and loads fitted parameters from dictionary."""
        scaler = cls(
            feature_names=data.get("feature_names", FEATURE_NAMES),
            quantile_range=tuple(data.get("quantile_range", (25.0, 75.0))),
            eps=data.get("eps", 1e-6),
        )
        scaler.center_ = np.array(data["center"], dtype=np.float32)
        scaler.scale_ = np.array(data["scale"], dtype=np.float32)
        scaler.n_features_in_ = data.get("n_features_in", len(scaler.center_))
        scaler.is_fitted = True
        return scaler

    def save(self, joblib_path: Union[str, Path], json_path: Optional[Union[str, Path]] = None) -> None:
        """Saves scaler to joblib binary and optional JSON config."""
        joblib_p = Path(joblib_path)
        joblib_p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, joblib_p)

        if json_path is not None:
            json_p = Path(json_path)
            json_p.parent.mkdir(parents=True, exist_ok=True)
            with open(json_p, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "TourSafeRobustScaler":
        """Loads scaler from either joblib binary or JSON file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Scaler file not found at {p}")

        if p.suffix == ".json":
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        else:
            loaded = joblib.load(p)
            if not isinstance(loaded, cls):
                # Fallback if unpickled differently
                pass
            return loaded
