"""
TourSafe Benchmark IMU Dataset Loaders & Adapters.
Provides parsers and standardizers for recognized IMU anomaly and HAR datasets:
- MobiAct (ADLs and Falls, smartphone IMU)
- SisFall (Fall and Movement activities across young & elderly subjects)
- UCI HAR (Smartphone Human Activity Recognition)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class BenchmarkDatasetAdapter:
    """
    Standardizes third-party raw IMU datasets into TourSafe's canonical trial structure:
    trial: {
        "subject_id": str,
        "activity": str,
        "is_anomaly": bool,
        "timestamps_sec": np.ndarray (N,),
        "accel": np.ndarray (N, 3) [ax, ay, az] in g,
        "gyro": np.ndarray (N, 3) [gx, gy, gz] in rad/s,
    }
    """

    # Recognized standard labels
    FALL_KEYWORDS = {"fall", "drop", "collapse", "slip", "trip", "impact", "faint", "fold"}

    @classmethod
    def is_activity_anomalous(cls, activity_name: str) -> bool:
        low = activity_name.lower()
        return any(k in low for k in cls.FALL_KEYWORDS)

    @classmethod
    def load_mobiact_csv(
        cls,
        file_path: Union[str, Path],
        subject_id: Optional[str] = None,
        activity_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parses a MobiAct CSV format recording file.
        Typical columns: timestamp/rel_time, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
        Acceleration in MobiAct is in m/s^2 (converted here to g by / 9.80665).
        Gyroscope is in rad/s or deg/s.
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"MobiAct file not found: {p}")

        df = pd.read_csv(p)
        cols_lower = {c: c.lower().strip() for c in df.columns}
        df.rename(columns=cols_lower, inplace=True)

        # Extract timestamps
        if "timestamp" in df.columns:
            ts = df["timestamp"].values.astype(np.float64)
            # If timestamp in ns or ms, normalize to seconds starting at 0
            if ts[0] > 1e12:  # ns
                ts = (ts - ts[0]) / 1e9
            elif ts[0] > 1e9: # ms
                ts = (ts - ts[0]) / 1e3
            else:
                ts = ts - ts[0]
        else:
            # Assume 200 Hz default for MobiAct if missing
            ts = np.arange(len(df), dtype=np.float64) / 200.0

        # Acceleration channels (m/s^2 -> g)
        ax_col = next((c for c in df.columns if "acc" in c and "x" in c), None)
        ay_col = next((c for c in df.columns if "acc" in c and "y" in c), None)
        az_col = next((c for c in df.columns if "acc" in c and "z" in c), None)

        if ax_col and ay_col and az_col:
            ax = df[ax_col].values.astype(np.float32) / 9.80665
            ay = df[ay_col].values.astype(np.float32) / 9.80665
            az = df[az_col].values.astype(np.float32) / 9.80665
        else:
            raise ValueError(f"Could not identify 3-axis accelerometer columns in {p}")

        # Gyroscope channels (rad/s)
        gx_col = next((c for c in df.columns if "gyr" in c and "x" in c), None)
        gy_col = next((c for c in df.columns if "gyr" in c and "y" in c), None)
        gz_col = next((c for c in df.columns if "gyr" in c and "z" in c), None)

        if gx_col and gy_col and gz_col:
            gx = df[gx_col].values.astype(np.float32)
            gy = df[gy_col].values.astype(np.float32)
            gz = df[gz_col].values.astype(np.float32)
        else:
            gx = np.zeros_like(ax)
            gy = np.zeros_like(ay)
            gz = np.zeros_like(az)

        act = activity_label or p.stem.split("_")[0]
        sub = subject_id or (p.stem.split("_")[1] if len(p.stem.split("_")) > 1 else "SUB_01")

        return {
            "subject_id": sub,
            "activity": act,
            "is_anomaly": cls.is_activity_anomalous(act),
            "trial_id": p.stem,
            "timestamps_sec": ts,
            "accel": np.stack([ax, ay, az], axis=1),
            "gyro": np.stack([gx, gy, gz], axis=1),
        }

    @classmethod
    def load_sisfall_txt(
        cls,
        file_path: Union[str, Path],
        subject_id: Optional[str] = None,
        activity_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parses a SisFall TXT format recording file (sampled at 200 Hz).
        SisFall ADLs are coded as D01..D19 and Falls as F01..F15.
        Sensors: ADXL345 (accel in bits -> g via 2 * 16 / 8192 or similar scale), ITG3200 (gyro in bits -> rad/s).
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"SisFall file not found: {p}")

        raw_data = np.loadtxt(p, delimiter=",", dtype=np.float32)
        # Columns: [acc1_x, acc1_y, acc1_z, gyro_x, gyro_y, gyro_z, acc2_x, acc2_y, acc2_z]
        # ADXL345 resolution ±16g with 13-bit: scale = (2 * 16.0) / 8192.0
        accel_scale = 32.0 / 8192.0
        # ITG3200 resolution ±2000 deg/s with 16-bit: scale = (2 * 2000.0) / 65536.0 * (pi / 180)
        gyro_scale = (4000.0 / 65536.0) * (np.pi / 180.0)

        ax = raw_data[:, 0] * accel_scale
        ay = raw_data[:, 1] * accel_scale
        az = raw_data[:, 2] * accel_scale

        gx = raw_data[:, 3] * gyro_scale
        gy = raw_data[:, 4] * gyro_scale
        gz = raw_data[:, 5] * gyro_scale

        ts = np.arange(len(raw_data), dtype=np.float64) / 200.0
        filename = p.stem
        is_fall = filename.upper().startswith("F") or "FALL" in filename.upper()
        act = activity_label or ("fall" if is_fall else "adl")

        return {
            "subject_id": subject_id or (filename.split("_")[1] if "_" in filename else "SUB_01"),
            "activity": act,
            "is_anomaly": is_fall,
            "trial_id": filename,
            "timestamps_sec": ts,
            "accel": np.stack([ax, ay, az], axis=1),
            "gyro": np.stack([gx, gy, gz], axis=1),
        }
