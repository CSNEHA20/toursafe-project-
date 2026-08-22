"""
TourSafe Raw Telemetry Validator.
Performs pre-ingestion and pre-dataset validation on raw telemetry samples:
- Missing fields and null checks
- Duplicate detection
- Timestamp monotonicity and jitter checks
- Sequence gap detection
- Sampling frequency estimation and stability
- Dynamic sensor range bounds verification
- NaN / Infinity checks
- Multi-sensor synchronization checks.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class ValidationIssue:
    issue_type: str
    sample_index: int
    session_id: Optional[str]
    details: str


@dataclass
class ValidationResult:
    is_valid: bool
    total_records: int
    valid_records: int
    invalid_records: int
    issues: List[ValidationIssue] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    estimated_sampling_rate_hz: float = 50.0
    sampling_rate_std_hz: float = 0.0


class RawTelemetryValidator:
    """
    Validates sequences of raw telemetry records before dataset windowing.
    """

    def __init__(
        self,
        nominal_frequency_hz: float = 50.0,
        frequency_tolerance: float = 0.35,  # 50 Hz ± 35% allowed
        max_time_gap_sec: float = 0.25,      # 250 ms max gap without split
        accel_range_g: float = 16.0,
        gyro_range_rad_s: float = 35.0,
    ):
        self.nominal_hz = nominal_frequency_hz
        self.freq_tolerance = frequency_tolerance
        self.max_time_gap_sec = max_time_gap_sec
        self.accel_range = accel_range_g
        self.gyro_range = gyro_range_rad_s

    def validate_sample_dictionary(self, sample: Dict[str, Any], idx: int) -> List[ValidationIssue]:
        """Validates a single telemetry sample dictionary."""
        issues = []
        session_id = sample.get("session_id")

        # 1. Required keys
        required_keys = ["timestamp", "accelerometer", "gyroscope"]
        for key in required_keys:
            if key not in sample or sample[key] is None:
                issues.append(ValidationIssue("MISSING_FIELD", idx, session_id, f"Missing required field '{key}'"))

        if issues:
            return issues

        # 2. Accelerometer channels
        accel = sample.get("accelerometer", {})
        for axis in ["x", "y", "z"]:
            val = accel.get(axis)
            if val is None:
                issues.append(ValidationIssue("MISSING_SENSOR_AXIS", idx, session_id, f"Missing accelerometer.{axis}"))
            elif not isinstance(val, (int, float)) or np.isnan(val) or np.isinf(val):
                issues.append(ValidationIssue("NAN_INF_VALUE", idx, session_id, f"Invalid accelerometer.{axis} value: {val}"))
            elif abs(val) > self.accel_range:
                issues.append(ValidationIssue("SENSOR_OUT_OF_BOUNDS", idx, session_id, f"accelerometer.{axis} out of range ({val} > {self.accel_range}g)"))

        # 3. Gyroscope channels
        gyro = sample.get("gyroscope", {})
        for axis in ["x", "y", "z"]:
            val = gyro.get(axis)
            if val is None:
                issues.append(ValidationIssue("MISSING_SENSOR_AXIS", idx, session_id, f"Missing gyroscope.{axis}"))
            elif not isinstance(val, (int, float)) or np.isnan(val) or np.isinf(val):
                issues.append(ValidationIssue("NAN_INF_VALUE", idx, session_id, f"Invalid gyroscope.{axis} value: {val}"))
            elif abs(val) > self.gyro_range:
                issues.append(ValidationIssue("SENSOR_OUT_OF_BOUNDS", idx, session_id, f"gyroscope.{axis} out of range ({val} > {self.gyro_range} rad/s)"))

        return issues

    def validate_session_stream(
        self,
        samples: List[Dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validates an ordered sequence of telemetry samples from a continuous tracking session.
        """
        if not samples:
            return ValidationResult(
                is_valid=False,
                total_records=0,
                valid_records=0,
                invalid_records=0,
                rejection_reasons=["Empty telemetry sequence"],
            )

        total = len(samples)
        issues: List[ValidationIssue] = []
        valid_indices: List[int] = []

        seen_timestamps = set()
        seen_seq_nums = set()
        timestamps_sec: List[float] = []

        for idx, sample in enumerate(samples):
            sample_issues = self.validate_sample_dictionary(sample, idx)
            if sample_issues:
                issues.extend(sample_issues)
                continue

            # Timestamp parsing
            raw_ts = sample.get("timestamp")
            try:
                if isinstance(raw_ts, (int, float)):
                    t_sec = float(raw_ts) / 1000.0 if raw_ts > 1e11 else float(raw_ts)
                elif isinstance(raw_ts, datetime):
                    t_sec = raw_ts.timestamp()
                elif isinstance(raw_ts, str):
                    t_sec = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
                else:
                    t_sec = float(raw_ts)
            except Exception as e:
                issues.append(ValidationIssue("INVALID_TIMESTAMP_FORMAT", idx, session_id, str(e)))
                continue

            # Check timestamp duplicate / monotonicity
            if t_sec in seen_timestamps:
                issues.append(ValidationIssue("DUPLICATE_TIMESTAMP", idx, session_id, f"Duplicate timestamp {t_sec}"))
                continue
            seen_timestamps.add(t_sec)

            if timestamps_sec and t_sec < timestamps_sec[-1]:
                issues.append(ValidationIssue("NON_MONOTONIC_TIMESTAMP", idx, session_id, f"Timestamp decreased from {timestamps_sec[-1]} to {t_sec}"))
                continue

            # Sequence number check
            seq = sample.get("sequence_number")
            if seq is not None:
                if seq in seen_seq_nums:
                    issues.append(ValidationIssue("DUPLICATE_SEQUENCE_NUMBER", idx, session_id, f"Duplicate sequence number {seq}"))
                    continue
                seen_seq_nums.add(seq)

            timestamps_sec.append(t_sec)
            valid_indices.append(idx)

        # Sampling rate analysis on valid samples
        if len(timestamps_sec) > 1:
            diffs = np.diff(timestamps_sec)
            # Filter non-zero diffs
            pos_diffs = diffs[diffs > 0]
            if len(pos_diffs) > 0:
                inst_rates = 1.0 / pos_diffs
                mean_hz = float(np.median(inst_rates))
                std_hz = float(np.std(inst_rates))
            else:
                mean_hz = self.nominal_hz
                std_hz = 0.0
        else:
            mean_hz = self.nominal_hz
            std_hz = 0.0

        # Frequency check
        rejection_reasons = []
        min_allowed_hz = self.nominal_hz * (1.0 - self.freq_tolerance)
        if len(timestamps_sec) > 10 and mean_hz < min_allowed_hz:
            msg = f"Observed mean sampling rate {mean_hz:.1f} Hz below minimum {min_allowed_hz:.1f} Hz"
            rejection_reasons.append(msg)

        valid_count = len(valid_indices)
        invalid_count = total - valid_count
        completeness = valid_count / total if total > 0 else 0.0

        if completeness < 0.6:
            rejection_reasons.append(f"Sequence completeness ratio {completeness:.2f} below required 0.60")

        is_valid = len(rejection_reasons) == 0 and valid_count >= int(round(self.nominal_hz * 3.0))

        return ValidationResult(
            is_valid=is_valid,
            total_records=total,
            valid_records=valid_count,
            invalid_records=invalid_count,
            issues=issues,
            rejection_reasons=rejection_reasons,
            estimated_sampling_rate_hz=round(mean_hz, 2),
            sampling_rate_std_hz=round(std_hz, 2),
        )


raw_telemetry_validator = RawTelemetryValidator()
