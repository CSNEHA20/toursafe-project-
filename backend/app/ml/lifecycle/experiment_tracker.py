"""
TourSafe ML Experiment Tracking Service.
Persists and queries training experiments in MongoDB collection 'ml_experiments'
for hyperparameter and metric comparisons.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from ...core import database as db_core
from ...schemas.ml_lifecycle import ExperimentRecord

logger = logging.getLogger("toursafe.ml.experiments")


class ExperimentTracker:
    """
    Persists and indexes training experiments.
    """

    async def init_indexes(self):
        try:
            db = db_core.get_database()
            await db.ml_experiments.create_index("experiment_id", unique=True)
            await db.ml_experiments.create_index("model_version")
            await db.ml_experiments.create_index("created_at")
        except Exception as e:
            logger.warning(f"Could not initialize ml_experiments indexes: {e}")

    async def log_experiment(self, experiment: ExperimentRecord) -> bool:
        db = db_core.get_database()
        try:
            await db.ml_experiments.insert_one(experiment.model_dump())
            logger.info(f"Logged experiment {experiment.experiment_id} for model {experiment.model_version}")
            return True
        except Exception as e:
            logger.error(f"Failed to log experiment: {e}")
            return False

    async def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        db = db_core.get_database()
        doc = await db.ml_experiments.find_one({"experiment_id": experiment_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return ExperimentRecord.model_validate(doc)

    async def list_experiments(self, limit: int = 50) -> List[ExperimentRecord]:
        db = db_core.get_database()
        cursor = db.ml_experiments.find({}).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                results.append(ExperimentRecord.model_validate(doc))
            except Exception as e:
                logger.error(f"Error parsing experiment doc: {e}")
        return results


experiment_tracker = ExperimentTracker()
