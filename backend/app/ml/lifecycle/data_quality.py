"""
TourSafe Data Quality Reporter.
Compiles comprehensive quality metrics, issue counts, and rejection reports
across multi-session telemetry datasets.
"""

from typing import List, Optional
from ...schemas.ml_lifecycle import DataQualitySummary
from .data_validator import ValidationResult


class DataQualityReporter:
    """
    Compiles multiple session validation outcomes into a dataset-level quality summary.
    """

    @staticmethod
    def compile_summary(
        results: List[ValidationResult],
        total_sessions: int,
        total_subjects: int,
    ) -> DataQualitySummary:
        total_inspected = sum(r.total_records for r in results)
        valid_count = sum(r.valid_records for r in results)
        invalid_count = sum(r.invalid_records for r in results)

        missing_fields = 0
        sequence_gaps = 0
        timestamp_jitter = 0
        duplicate_samples = 0
        nan_inf = 0

        rejection_reasons = []

        for r in results:
            if not r.is_valid and r.rejection_reasons:
                rejection_reasons.extend(r.rejection_reasons)

            for issue in r.issues:
                if "MISSING" in issue.issue_type:
                    missing_fields += 1
                elif "GAP" in issue.issue_type:
                    sequence_gaps += 1
                elif "TIMESTAMP" in issue.issue_type:
                    timestamp_jitter += 1
                elif "DUPLICATE" in issue.issue_type:
                    duplicate_samples += 1
                elif "NAN_INF" in issue.issue_type or "OUT_OF_BOUNDS" in issue.issue_type:
                    nan_inf += 1

        sampling_rates = [r.estimated_sampling_rate_hz for r in results if r.valid_records > 0]
        mean_hz = float(sum(sampling_rates) / len(sampling_rates)) if sampling_rates else 50.0

        completeness = valid_count / total_inspected if total_inspected > 0 else 0.0
        passed = valid_count > 0 and (valid_count / total_inspected >= 0.70) if total_inspected > 0 else False

        unique_reasons = list(dict.fromkeys(rejection_reasons))

        return DataQualitySummary(
            total_samples_inspected=total_inspected,
            valid_samples_count=valid_count,
            invalid_samples_count=invalid_count,
            removed_samples_count=invalid_count,
            missing_fields_count=missing_fields,
            sequence_gaps_count=sequence_gaps,
            timestamp_jitter_count=timestamp_jitter,
            duplicate_samples_count=duplicate_samples,
            nan_inf_count=nan_inf,
            session_count=total_sessions,
            subject_count=total_subjects,
            mean_sampling_rate_hz=round(mean_hz, 2),
            sampling_rate_std_hz=0.0,
            completeness_ratio=round(completeness, 4),
            passed_validation=passed,
            rejection_reasons=unique_reasons[:10],
        )


data_quality_reporter = DataQualityReporter()
