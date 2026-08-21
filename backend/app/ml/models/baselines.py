"""
TourSafe ML Baseline Models.
Provides benchmark baselines for anomaly detection comparison:
1. Kinematic Peak Magnitude Detector (Rule-based acceleration threshold)
2. Isolation Forest Detector (Summary statistical features over temporal window)
3. PCA Reconstruction Detector (Linear subspace projection baseline)
"""

from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest


class KinematicPeakDetector:
    """
    Rule-based baseline: detects anomalies based on maximum acceleration vector magnitude.
    Threshold typically tuned on normal validation peak distributions (e.g. 99th percentile).
    """

    def __init__(self, threshold_g: float = 3.0):
        self.threshold_g = float(threshold_g)
        self.fitted_max_normal_g: float = 0.0

    def fit(self, X: np.ndarray, y: Optional[Any] = None) -> "KinematicPeakDetector":
        """
        X: shape (N, T, D) where feature 6 or channels 0..2 are acceleration.
        """
        scores = self.compute_peak_scores(X)
        self.fitted_max_normal_g = float(np.percentile(scores, 99.0))
        # Default calibrated threshold = 99th percentile + safety margin
        self.threshold_g = max(2.5, self.fitted_max_normal_g * 1.3)
        return self

    def compute_peak_scores(self, X: np.ndarray) -> np.ndarray:
        """
        Returns maximum acceleration magnitude across the 150 timesteps per sample.
        """
        X_arr = np.asarray(X, dtype=np.float32)
        if X_arr.shape[-1] == 8:
            # Channel 6 is accel_mag
            accel_mags = X_arr[:, :, 6]
        else:
            # Channel 0, 1, 2 are ax, ay, az
            accel_mags = np.sqrt(np.sum(np.square(X_arr[:, :, 0:3]), axis=-1))

        return np.max(accel_mags, axis=1)

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        return self.compute_peak_scores(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        scores = self.predict_scores(X)
        return (scores > self.threshold_g).astype(int)


class IsolationForestDetector:
    """
    Feature-engineered baseline: computes statistical summary moments
    (mean, std, min, max, RMS, crest factor) per channel across the window,
    then trains an IsolationForest outlier estimator.
    """

    def __init__(self, n_estimators: int = 100, contamination: float = 0.05, random_state: int = 42):
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
        )

    def _extract_window_features(self, X: np.ndarray) -> np.ndarray:
        """
        Transforms (N, T, D) -> (N, D * 6) statistical summary vectors.
        """
        N, T, D = X.shape
        mean_feat = np.mean(X, axis=1)
        std_feat = np.std(X, axis=1)
        min_feat = np.min(X, axis=1)
        max_feat = np.max(X, axis=1)
        rms_feat = np.sqrt(np.mean(np.square(X), axis=1))
        p2p_feat = max_feat - min_feat

        return np.concatenate(
            [mean_feat, std_feat, min_feat, max_feat, rms_feat, p2p_feat],
            axis=1,
        )

    def fit(self, X: np.ndarray, y: Optional[Any] = None) -> "IsolationForestDetector":
        feats = self._extract_window_features(X)
        self.model.fit(feats)
        return self

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        """
        Returns inverted anomaly score (higher = more anomalous).
        sklearn decision_function returns negative values for anomalies, so we negate it.
        """
        feats = self._extract_window_features(X)
        return -self.model.decision_function(feats)

    def predict(self, X: np.ndarray) -> np.ndarray:
        feats = self._extract_window_features(X)
        preds = self.model.predict(feats)  # -1 = anomaly, 1 = normal
        return (preds == -1).astype(int)


class PCAReconstructionDetector:
    """
    Linear subspace baseline: fits PCA on flattened normal windows and
    measures L2 reconstruction error as anomaly score.
    """

    def __init__(self, n_components: int = 16):
        self.pca = PCA(n_components=n_components)

    def fit(self, X: np.ndarray, y: Optional[Any] = None) -> "PCAReconstructionDetector":
        N, T, D = X.shape
        X_flat = X.reshape(N, T * D)
        self.pca.fit(X_flat)
        return self

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        N, T, D = X.shape
        X_flat = X.reshape(N, T * D)
        proj = self.pca.transform(X_flat)
        recon = self.pca.inverse_transform(proj)
        mse = np.mean(np.square(X_flat - recon), axis=1)
        return mse
