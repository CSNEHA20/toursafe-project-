"""
TourSafe Asynchronous ML Training Manager.
Coordinates reproducible training jobs, scaler fitting, LSTM autoencoder optimization,
threshold calibration, artifact packaging, experiment logging, and model registration.
Guarantees newly trained models remain in 'TRAINED' state until human governance approval.
"""

import asyncio
from datetime import datetime, timezone
import logging
import platform
import sys
import time
from typing import Any, Dict, List, Optional
import numpy as np
import torch

from ...core import database as db_core
from ...schemas.ml_lifecycle import (
    ExperimentRecord,
    MLTrainingHyperparameters,
    ModelLifecycleStatus,
    TrainingJobRecord,
    TrainingJobStatus,
)
from ..config import ModelConfig, TrainingConfig
from ..evaluation.evaluator import ModelEvaluator
from ..evaluation.threshold import AnomalyThresholdCalibrator
from ..models.lstm_autoencoder import TourSafeLSTMAutoencoder
from ..preprocessing.scaler import TourSafeRobustScaler
from ..training.trainer import AutoencoderTrainer
from .dataset_builder import dataset_builder
from .experiment_tracker import experiment_tracker
from .model_packager import model_packager
from .model_registry import model_registry

logger = logging.getLogger("toursafe.ml.training_manager")


class MLTrainingManager:
    """
    Manages background training tasks and job execution lifecycle.
    """

    def __init__(self):
        self._running_tasks: Dict[str, asyncio.Task] = {}

    async def init_indexes(self):
        try:
            db = db_core.get_database()
            await db.ml_training_jobs.create_index("job_id", unique=True)
            await db.ml_training_jobs.create_index("model_version")
            await db.ml_training_jobs.create_index("status")
        except Exception as e:
            logger.warning(f"Could not initialize ml_training_jobs indexes: {e}")

    async def create_training_job(
        self,
        model_version: str,
        dataset_version: str,
        hyperparameters: Optional[MLTrainingHyperparameters] = None,
        feature_version: str = "features_v1",
        created_by: str = "system",
    ) -> TrainingJobRecord:
        """
        Creates and queues a new training job.
        """
        existing_model = await model_registry.get_model(model_version)
        if existing_model:
            raise ValueError(f"Model version '{model_version}' already exists in registry! Use a new version identifier.")

        job = TrainingJobRecord(
            model_version=model_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            status=TrainingJobStatus.QUEUED,
            hyperparameters=hyperparameters or MLTrainingHyperparameters(),
            created_by=created_by,
        )

        db = db_core.get_database()
        await db.ml_training_jobs.insert_one(job.model_dump())
        logger.info(f"Queued training job {job.job_id} for target model {model_version}")

        # Spawn asynchronous execution
        task = asyncio.create_task(self._execute_training_job(job.job_id))
        self._running_tasks[job.job_id] = task

        return job

    async def get_training_job(self, job_id: str) -> Optional[TrainingJobRecord]:
        db = db_core.get_database()
        doc = await db.ml_training_jobs.find_one({"job_id": job_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return TrainingJobRecord.model_validate(doc)

    async def list_training_jobs(self, limit: int = 50) -> List[TrainingJobRecord]:
        db = db_core.get_database()
        cursor = db.ml_training_jobs.find({}).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                results.append(TrainingJobRecord.model_validate(doc))
            except Exception as e:
                logger.error(f"Error parsing training job doc: {e}")
        return results

    async def cancel_job(self, job_id: str) -> bool:
        if job_id in self._running_tasks:
            self._running_tasks[job_id].cancel()
            del self._running_tasks[job_id]

        db = db_core.get_database()
        res = await db.ml_training_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": TrainingJobStatus.CANCELLED.value}},
        )
        return res.modified_count > 0

    async def _execute_training_job(self, job_id: str):
        """Asynchronous worker executing the full ML training lifecycle."""
        db = db_core.get_database()
        t_start = time.time()

        try:
            # Update to RUNNING
            await db.ml_training_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": TrainingJobStatus.RUNNING.value,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )

            job_doc = await db.ml_training_jobs.find_one({"job_id": job_id})
            job = TrainingJobRecord.model_validate(job_doc)
            hp = job.hyperparameters

            # 1. Load Dataset Bundle
            X_train, X_val, X_test, y_test, ds_entry = dataset_builder.load_dataset_bundle(job.dataset_version)

            # 2. Fit Scaler ONLY on Train split (Strict anti-leakage)
            scaler = TourSafeRobustScaler()
            scaler.fit(X_train)

            X_train_scaled = scaler.transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            X_test_scaled = scaler.transform(X_test)

            # 3. Instantiate Architecture
            m_cfg = ModelConfig(
                input_dim=8,
                sequence_length=150,
                hidden_dims=hp.hidden_dims,
                latent_dim=hp.latent_dim,
                dropout=hp.dropout,
            )
            model = TourSafeLSTMAutoencoder(m_cfg)

            # 4. Train Model
            t_cfg = TrainingConfig(
                batch_size=hp.batch_size,
                learning_rate=hp.learning_rate,
                weight_decay=hp.weight_decay,
                epochs=hp.epochs,
                early_stopping_patience=hp.early_stopping_patience,
                lr_reduce_patience=hp.lr_reduce_patience,
                lr_reduce_factor=hp.lr_reduce_factor,
                clip_grad_norm=hp.clip_grad_norm,
                random_seed=hp.random_seed,
                device=hp.device,
            )
            trainer = AutoencoderTrainer(model, t_cfg)
            train_res = trainer.train(X_train_scaled, X_val_scaled, verbose=False)

            # 5. Calibrate Multi-tier Thresholds on Scaled Validation Set
            evaluator = ModelEvaluator(device=hp.device)
            val_scores = evaluator.compute_model_scores(train_res.best_model, X_val_scaled)
            calibrator = AnomalyThresholdCalibrator()
            thresh_res = calibrator.calibrate(val_scores, epoch=train_res.best_epoch)

            # 6. Evaluate Model on Scaled Test Set
            test_acts = ["benchmark"] * len(X_test)
            eval_report = evaluator.evaluate(
                model=train_res.best_model,
                X_test=X_test_scaled,
                y_test=y_test,
                test_activities=test_acts,
                threshold_result=thresh_res,
                X_train=X_train_scaled,
                X_val=X_val_scaled,
            )

            # 7. Package Complete Artifact Bundle with SHA-256 Checksums
            model_entry = model_packager.package_model(
                model=train_res.best_model,
                scaler=scaler,
                threshold_result=thresh_res,
                eval_report=eval_report,
                training_result=train_res,
                model_version=job.model_version,
                dataset_version=job.dataset_version,
                feature_version=job.feature_version,
                created_by=job.created_by,
            )

            # 8. Register Model in Registry with initial status 'TRAINED'
            model_entry.status = ModelLifecycleStatus.TRAINED
            await model_registry.register_model(model_entry)

            t_end = time.time()
            duration = t_end - t_start

            # 9. Log Experiment
            exp = ExperimentRecord(
                model_version=job.model_version,
                dataset_version=job.dataset_version,
                feature_version=job.feature_version,
                hyperparameters=hp.model_dump(),
                metrics=eval_report.to_dict(),
                thresholds=thresh_res.to_dict(),
                duration_seconds=round(duration, 2),
                hardware_info={"platform": platform.platform(), "processor": platform.processor()},
                python_version=sys.version,
                framework_version=f"torch-{torch.__version__}",
                random_seed=hp.random_seed,
            )
            await experiment_tracker.log_experiment(exp)

            # 10. Update Job as COMPLETED
            await db.ml_training_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": TrainingJobStatus.COMPLETED.value,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "duration_seconds": round(duration, 2),
                        "current_epoch": train_res.total_epochs,
                        "best_epoch": train_res.best_epoch,
                        "best_val_loss": round(train_res.best_val_loss, 6),
                        "train_loss_history": train_res.train_loss_history,
                        "val_loss_history": train_res.val_loss_history,
                        "experiment_id": exp.experiment_id,
                    }
                },
            )
            logger.info(f"✅ Training job {job_id} successfully completed for model {job.model_version}")

        except Exception as e:
            logger.error(f"❌ Training job {job_id} failed: {e}", exc_info=True)
            await db.ml_training_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": TrainingJobStatus.FAILED.value,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": str(e),
                    }
                },
            )
        finally:
            if job_id in self._running_tasks:
                del self._running_tasks[job_id]


training_manager = MLTrainingManager()
