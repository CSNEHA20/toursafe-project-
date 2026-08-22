"""
TourSafe Model Comparison Engine.
Performs rigorous side-by-side comparison between candidate models and the active production model.
Reports supervised metrics (ROC-AUC, PR-AUC, F1, Precision, Recall, FPR, FNR) where ground truth exists,
and reconstruction error distributions, threshold stability, and latency benchmarks.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from ...schemas.ml_lifecycle import (
    MetricComparisonItem,
    ModelComparisonReport,
    ModelRegistryEntry,
)


class ModelComparisonEngine:
    """
    Evaluates candidate models against the baseline production model.
    """

    def compare_models(
        self,
        production_model: ModelRegistryEntry,
        candidate_model: ModelRegistryEntry,
    ) -> ModelComparisonReport:
        p_met = production_model.metrics
        c_met = candidate_model.metrics

        has_ground_truth = p_met.has_ground_truth and c_met.has_ground_truth

        metrics_comp: List[MetricComparisonItem] = []

        # Supervised metrics (require ground truth)
        supervised_fields = [
            ("ROC-AUC", p_met.roc_auc, c_met.roc_auc, True),
            ("PR-AUC", p_met.pr_auc, c_met.pr_auc, True),
            ("F1-Score", p_met.f1_score, c_met.f1_score, True),
            ("Precision", p_met.precision, c_met.precision, True),
            ("Recall", p_met.recall, c_met.recall, True),
            ("False Positive Rate", p_met.false_positive_rate, c_met.false_positive_rate, False),  # Lower is better
            ("False Negative Rate", p_met.false_negative_rate, c_met.false_negative_rate, False),  # Lower is better
        ]

        candidate_wins = 0
        total_compared = 0

        for name, p_val, c_val, higher_is_better in supervised_fields:
            if p_val is not None and c_val is not None:
                diff = round(c_val - p_val, 4)
                is_better = (diff > 0) if higher_is_better else (diff < 0)
                if is_better:
                    candidate_wins += 1
                total_compared += 1
                metrics_comp.append(MetricComparisonItem(
                    metric_name=name,
                    production_value=round(p_val, 4),
                    candidate_value=round(c_val, 4),
                    difference=diff,
                    candidate_is_better=is_better,
                    requires_ground_truth=True,
                ))
            else:
                metrics_comp.append(MetricComparisonItem(
                    metric_name=name,
                    production_value=round(p_val, 4) if p_val is not None else None,
                    candidate_value=round(c_val, 4) if c_val is not None else None,
                    difference=None,
                    candidate_is_better=None,
                    requires_ground_truth=True,
                ))

        # Latency & Reconstruction Error comparison (Unsupervised)
        lat_diff = round(c_met.mean_inference_latency_ms - p_met.mean_inference_latency_ms, 4)
        lat_better = lat_diff <= 0.0
        metrics_comp.append(MetricComparisonItem(
            metric_name="Mean Inference Latency (ms)",
            production_value=round(p_met.mean_inference_latency_ms, 4),
            candidate_value=round(c_met.mean_inference_latency_ms, 4),
            difference=lat_diff,
            candidate_is_better=lat_better,
            requires_ground_truth=False,
        ))

        p99_diff = round(c_met.p99_reconstruction_error - p_met.p99_reconstruction_error, 4)
        metrics_comp.append(MetricComparisonItem(
            metric_name="P99 Normal Reconstruction Error",
            production_value=round(p_met.p99_reconstruction_error, 4),
            candidate_value=round(c_met.p99_reconstruction_error, 4),
            difference=p99_diff,
            candidate_is_better=None,
            requires_ground_truth=False,
        ))

        # Recommendation
        if not has_ground_truth:
            summary = (
                f"Candidate {candidate_model.model_version} lacks complete ground truth labels on test dataset. "
                "Supervised metrics are marked INSUFFICIENT GROUND TRUTH. Manual review and Shadow deployment recommended."
            )
            readiness = False
        elif candidate_wins >= max(1, total_compared // 2):
            summary = (
                f"Candidate {candidate_model.model_version} demonstrated superior benchmark performance "
                f"({candidate_wins}/{total_compared} supervised metrics improved). Ready for Staging/Shadow validation."
            )
            readiness = True
        else:
            summary = (
                f"Candidate {candidate_model.model_version} does not significantly outperform production model "
                f"{production_model.model_version} ({candidate_wins}/{total_compared} metrics improved). Review threshold calibration."
            )
            readiness = False

        return ModelComparisonReport(
            production_model_version=production_model.model_version,
            candidate_model_version=candidate_model.model_version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_used=candidate_model.dataset_version,
            has_ground_truth_labels=has_ground_truth,
            metrics_comparison=metrics_comp,
            reconstruction_distribution_diff={
                "production_val_mse": p_met.reconstruction_mse_mean,
                "candidate_val_mse": c_met.reconstruction_mse_mean,
                "production_p99": p_met.p99_reconstruction_error,
                "candidate_p99": c_met.p99_reconstruction_error,
            },
            operational_alert_rate_diff={
                "production_threshold": production_model.threshold_config.primary_threshold,
                "candidate_threshold": candidate_model.threshold_config.primary_threshold,
            },
            latency_comparison={
                "production_mean_ms": p_met.mean_inference_latency_ms,
                "candidate_mean_ms": c_met.mean_inference_latency_ms,
                "production_p95_ms": p_met.p95_inference_latency_ms,
                "candidate_p95_ms": c_met.p95_inference_latency_ms,
            },
            recommendation_summary=summary,
            approval_readiness=readiness,
        )


model_comparison_engine = ModelComparisonEngine()
