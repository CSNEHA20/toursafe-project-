"""
TourSafe ML End-to-End Pipeline Orchestrator.
Orchestrates dataset generation, subject-wise splitting, robust scaling,
LSTM Autoencoder training, threshold calibration, comprehensive evaluation,
and versioned artifact export.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

from .config import PipelineConfig, default_pipeline_config
from .dataset.dataset_builder import DatasetBuilder, DatasetBundle
from .dataset.synthetic_generator import SyntheticIMUGenerator
from .evaluation.evaluator import AnomalyEvaluationReport, ModelEvaluator
from .evaluation.threshold import AnomalyThresholdCalibrator, ThresholdCalibrationResult
from .models.lstm_autoencoder import TourSafeLSTMAutoencoder
from .preprocessing.scaler import TourSafeRobustScaler
from .training.trainer import AutoencoderTrainer, TrainingResult
from .artifacts.manager import ModelArtifactManager


class MLTrainingPipeline:
    """
    Coordinates the full ML training lifecycle for TourSafe's LSTM Autoencoder.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or default_pipeline_config
        self.artifact_manager = ModelArtifactManager(self.config.artifact)
        self.dataset_builder = DatasetBuilder(self.config.window)
        self.calibrator = AnomalyThresholdCalibrator()
        self.evaluator = ModelEvaluator(device=self.config.training.device)

    def run(
        self,
        n_train_subjects: int = 14,
        n_val_subjects: int = 3,
        n_test_subjects: int = 4,
        verbose: bool = True,
    ) -> Tuple[TourSafeLSTMAutoencoder, TourSafeRobustScaler, ThresholdCalibrationResult, AnomalyEvaluationReport, Dict[str, Any]]:
        """
        Executes complete training and evaluation pipeline:
        1. Multi-subject IMU dataset generation with strict anti-leakage splitting
        2. Window extraction & uniform 50 Hz resampling (150 steps @ 8 channels)
        3. Robust scaler fitting strictly on training normal data
        4. LSTM Autoencoder training with early stopping
        5. Statistical threshold calibration on validation normal errors
        6. Comprehensive test set evaluation & baseline comparisons
        7. Model artifact export (PyTorch weights, ONNX, Scaler, Thresholds, Metadata)
        """
        if verbose:
            print("=" * 70)
            print(" TOURSAFE ML PIPELINE: LSTM AUTOENCODER TRAINING & EVALUATION")
            print("=" * 70)

        # ---------------------------------------------------------
        # Step 1: Ingest & Partition Multi-Subject Cohort
        # ---------------------------------------------------------
        if verbose:
            print("\n[1/6] Generating & partitioning multi-subject IMU cohorts...")
        generator = SyntheticIMUGenerator(
            target_hz=self.config.window.nominal_frequency_hz,
            random_seed=self.config.training.random_seed,
        )
        train_trials, val_trials, test_trials = generator.generate_cohort(
            n_train_subjects=n_train_subjects,
            n_val_subjects=n_val_subjects,
            n_test_subjects=n_test_subjects,
        )

        dataset_bundle: DatasetBundle = self.dataset_builder.build_dataset_bundle(
            train_trials=train_trials,
            val_trials=val_trials,
            test_trials=test_trials,
        )

        if verbose:
            s = dataset_bundle.summary
            print(f"  • Train Windows (Normal Only):   {s['n_train_windows']} from {s['n_train_subjects']} subjects")
            print(f"  • Val Windows (Normal Only):     {s['n_val_windows']} from {s['n_val_subjects']} subjects")
            print(f"  • Test Windows (Normal+Anomaly): {s['n_test_windows']} ({s['n_test_normal_windows']} norm, {s['n_test_anomaly_windows']} anom) from {s['n_test_subjects']} subjects")
            print(f"  • Window Tensor Dimensions:      {dataset_bundle.X_train_normal.shape}")

        # ---------------------------------------------------------
        # Step 2: Fit Robust Scaler ONLY on Normal Training Data
        # ---------------------------------------------------------
        if verbose:
            print("\n[2/6] Fitting RobustScaler on normal training motion...")
        scaler = TourSafeRobustScaler(feature_names=self.config.features)
        X_train_scaled = scaler.fit_transform(dataset_bundle.X_train_normal)
        X_val_scaled = scaler.transform(dataset_bundle.X_val_normal)
        X_test_scaled = scaler.transform(dataset_bundle.X_test)

        if verbose:
            print(f"  • Scaler fitted on {len(X_train_scaled)} normal sequences across {scaler.n_features_in_} channels.")

        # ---------------------------------------------------------
        # Step 3: Initialize & Train PyTorch LSTM Autoencoder
        # ---------------------------------------------------------
        if verbose:
            print("\n[3/6] Initializing & Training LSTM Autoencoder...")
        model = TourSafeLSTMAutoencoder(self.config.model)
        trainer = AutoencoderTrainer(model=model, config=self.config.training)

        training_result: TrainingResult = trainer.train(
            X_train_scaled=X_train_scaled,
            X_val_scaled=X_val_scaled,
            verbose=verbose,
        )

        best_model = training_result.best_model

        # ---------------------------------------------------------
        # Step 4: Calibrate Anomaly Threshold on Validation Errors
        # ---------------------------------------------------------
        if verbose:
            print("\n[4/6] Calibrating anomaly thresholds on validation normal errors...")
        val_errors = self.evaluator.compute_model_scores(best_model, X_val_scaled)
        threshold_result: ThresholdCalibrationResult = self.calibrator.calibrate(
            val_reconstruction_errors=val_errors,
            method="percentile_99",
            epoch=training_result.best_epoch,
        )

        if verbose:
            print(f"  • Primary Anomaly Threshold: {threshold_result.primary_threshold:.6f}")
            print(f"  • Warning Anomaly Threshold: {threshold_result.warning_threshold:.6f}")
            print(f"  • Critical Anomaly Threshold: {threshold_result.critical_threshold:.6f}")
            print(f"  • Val Error Mean: {threshold_result.val_score_mean:.6f}, Std: {threshold_result.val_score_std:.6f}")

        # ---------------------------------------------------------
        # Step 5: Evaluate on Held-Out Test Set & Compare Baselines
        # ---------------------------------------------------------
        if verbose:
            print("\n[5/6] Evaluating on held-out test cohort & comparing baselines...")
        eval_report: AnomalyEvaluationReport = self.evaluator.evaluate(
            model=best_model,
            X_test=X_test_scaled,
            y_test=dataset_bundle.y_test,
            test_activities=dataset_bundle.test_activities,
            threshold_result=threshold_result,
            X_train=X_train_scaled,
            X_val=X_val_scaled,
        )

        if verbose:
            print(f"  • ROC-AUC Score:      {eval_report.roc_auc:.4f}")
            print(f"  • PR-AUC Score:       {eval_report.pr_auc:.4f}")
            print(f"  • Precision:          {eval_report.precision_at_calibrated_threshold:.4f}")
            print(f"  • Recall:             {eval_report.recall_at_calibrated_threshold:.4f}")
            print(f"  • F1-Score:           {eval_report.f1_at_calibrated_threshold:.4f}")
            print(f"  • Specificity:        {eval_report.specificity:.4f}")
            print(f"  • Confusion Matrix:   {eval_report.confusion_matrix}")
            print("\n  --- Baseline Comparison ---")
            for b_name, b_metrics in eval_report.baseline_comparisons.items():
                print(f"    - {b_name}: ROC-AUC={b_metrics.get('roc_auc', 'N/A')}, F1={b_metrics.get('f1_score', 'N/A')}")

        # ---------------------------------------------------------
        # Step 6: Export Versioned Artifact Bundle
        # ---------------------------------------------------------
        if verbose:
            print("\n[6/6] Exporting versioned artifact bundle...")
        metadata = self.artifact_manager.save_artifact_bundle(
            model=best_model,
            scaler=scaler,
            threshold_result=threshold_result,
            eval_report=eval_report,
            training_result=training_result,
            dataset_summary=dataset_bundle.summary,
            version=self.config.artifact.version,
        )

        if verbose:
            print(f"  • Artifacts successfully exported to: {self.config.artifact.version_dir}")
            print(f"  • ONNX Parity Status: {metadata['onnx_export']['parity_verified']} (Max diff: {metadata['onnx_export']['max_absolute_difference']})")
            print("=" * 70)
            print(" ML PIPELINE COMPLETE: ARTIFACT READY FOR INFERENCE")
            print("=" * 70)

        return best_model, scaler, threshold_result, eval_report, metadata


def main():
    parser = argparse.ArgumentParser(description="TourSafe ML LSTM Autoencoder Training Pipeline")
    parser.add_argument("--epochs", type=int, default=40, help="Maximum training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Training batch size")
    parser.add_argument("--version", type=str, default="v1.0.0", help="Model artifact version")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    cfg = PipelineConfig()
    cfg.training.epochs = args.epochs
    cfg.training.batch_size = args.batch_size
    cfg.training.random_seed = args.seed
    cfg.artifact.version = args.version

    pipeline = MLTrainingPipeline(cfg)
    pipeline.run(verbose=True)


if __name__ == "__main__":
    main()
