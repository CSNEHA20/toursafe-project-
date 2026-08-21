"""
TourSafe IMU Resampling Engine.
Provides uniform 50 Hz temporal resampling and interpolation for variable-rate
and jittered IMU sensor streams.
"""

from typing import List, Optional, Tuple, Union
import numpy as np
from scipy.interpolate import interp1d


class IMUResampler:
    """
    Resamples non-uniform, jittered raw IMU sensor timestamps to an exact,
    uniformly spaced 50 Hz temporal grid.
    """

    def __init__(self, target_hz: float = 50.0, max_gap_seconds: float = 0.250):
        self.target_hz = float(target_hz)
        self.target_dt = 1.0 / self.target_hz
        self.max_gap_seconds = float(max_gap_seconds)

    def resample_sequence(
        self,
        timestamps_sec: np.ndarray,
        sensor_values: np.ndarray,
        target_length: Optional[int] = None,
        duration_sec: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray, bool]:
        """
        Resamples a 1D/2D sensor array across time onto an exact 50 Hz grid.

        Parameters
        ----------
        timestamps_sec : np.ndarray
            Monotonic 1D array of relative or absolute timestamps in seconds.
        sensor_values : np.ndarray
            Shape (N, n_channels) or (N,) containing raw sensor measurements.
        target_length : Optional[int]
            Exact number of output samples required (e.g. 150 for 3 seconds @ 50 Hz).
        duration_sec : Optional[float]
            Total window duration in seconds. If provided and target_length is None,
            target_length = round(duration_sec * target_hz).

        Returns
        -------
        resampled_timestamps : np.ndarray
            1D array of uniformly spaced timestamps.
        resampled_values : np.ndarray
            Shape (target_length, n_channels) resampled values.
        is_valid : bool
            Whether interpolation was performed without encountering excessive time gaps.
        """
        timestamps_sec = np.asarray(timestamps_sec, dtype=np.float64)
        sensor_values = np.asarray(sensor_values, dtype=np.float64)

        if sensor_values.ndim == 1:
            sensor_values = sensor_values[:, np.newaxis]

        n_samples, n_channels = sensor_values.shape
        if n_samples < 2:
            raise ValueError(f"Resampling requires at least 2 input samples, got {n_samples}")

        # Check for timestamp monotonicity
        diffs = np.diff(timestamps_sec)
        if np.any(diffs <= 0):
            # Sort chronologically if small out-of-order jitter exists
            sort_indices = np.argsort(timestamps_sec)
            timestamps_sec = timestamps_sec[sort_indices]
            sensor_values = sensor_values[sort_indices]
            diffs = np.diff(timestamps_sec)

        # Check maximum gap tolerance
        max_gap = np.max(diffs) if len(diffs) > 0 else 0.0
        has_excessive_gap = bool(max_gap > self.max_gap_seconds)

        t_start = timestamps_sec[0]
        if duration_sec is not None:
            t_end = t_start + duration_sec
            if target_length is None:
                target_length = int(round(duration_sec * self.target_hz))
        else:
            t_end = timestamps_sec[-1]
            if target_length is None:
                span = max(1e-6, t_end - t_start)
                target_length = max(2, int(round(span * self.target_hz)))

        # Construct target uniform timestamps
        target_timestamps = np.linspace(t_start, t_end, target_length, endpoint=False)

        # Build interpolator per channel
        # Use linear interpolation with extrapolation clamped to boundary values
        interpolator = interp1d(
            timestamps_sec,
            sensor_values,
            axis=0,
            kind="linear",
            bounds_error=False,
            fill_value=(sensor_values[0], sensor_values[-1]),
        )

        resampled_values = interpolator(target_timestamps)
        is_valid = not has_excessive_gap

        return target_timestamps, resampled_values, is_valid

    def resample_window(
        self,
        samples: List[dict],
        feature_keys: List[str],
        window_duration_sec: float = 3.0,
        expected_samples: int = 150,
    ) -> Tuple[np.ndarray, bool]:
        """
        Convenience method to resample a list of dictionary samples (e.g. from TelemetrySample).
        """
        if len(samples) < 2:
            return np.zeros((expected_samples, len(feature_keys))), False

        # Extract timestamps in seconds relative to first sample
        t0 = samples[0]["timestamp_sec"]
        ts = np.array([s["timestamp_sec"] - t0 for s in samples], dtype=np.float64)
        vals = np.array([[s[k] for k in feature_keys] for s in samples], dtype=np.float64)

        _, resampled_vals, is_valid = self.resample_sequence(
            timestamps_sec=ts,
            sensor_values=vals,
            target_length=expected_samples,
            duration_sec=window_duration_sec,
        )

        return resampled_vals, is_valid
