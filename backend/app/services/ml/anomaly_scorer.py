"""
TourSafe Anomaly Scorer.
Calculates reconstruction error anomaly scores matching Prompt 8 evaluation standard:
Mean Squared Error (MSE) between original normalized sequence and LSTM autoencoder reconstruction.
"""

from typing import Dict, Tuple
import numpy as np

from ...ml.config import FEATURE_NAMES


class AnomalyScorer:
    """
    Computes numerical anomaly metrics from original and reconstructed IMU tensors.
    """

    @staticmethod
    def compute_mse_score(
        x_original: np.ndarray,
        x_reconstructed: np.ndarray,
    ) -> float:
        """
        Computes overall Mean Squared Error (MSE) across all timesteps and channels.
        MSE = (1 / (T * D)) * sum((X - X_hat)^2)
        """
        diff = np.asarray(x_original, dtype=np.float32) - np.asarray(x_reconstructed, dtype=np.float32)
        mse = float(np.mean(np.square(diff)))
        return max(0.0, mse)

    @staticmethod
    def compute_channel_breakdown(
        x_original: np.ndarray,
        x_reconstructed: np.ndarray,
    ) -> Dict[str, float]:
        """
        Computes per-channel MSE for detailed ML observability and debugging.
        """
        diff = np.asarray(x_original, dtype=np.float32) - np.asarray(x_reconstructed, dtype=np.float32)
        # Squeeze batch dimension if present
        if diff.ndim == 3:
            diff = diff[0]

        channel_mse = np.mean(np.square(diff), axis=0)
        breakdown = {}
        for idx, feat in enumerate(FEATURE_NAMES):
            if idx < len(channel_mse):
                breakdown[feat] = round(float(channel_mse[idx]), 6)

        return breakdown


anomaly_scorer = AnomalyScorer()
