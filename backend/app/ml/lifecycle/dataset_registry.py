"""
TourSafe Dataset Registry Service.
Manages immutable dataset records, version queries, quality inspection,
and metadata indexing in MongoDB collection 'ml_datasets'.
"""

import logging
from typing import Any, Dict, List, Optional
from pymongo.errors import DuplicateKeyError

from ...core import database as db_core
from ...schemas.ml_lifecycle import DatasetRegistryEntry, DatasetStatus

logger = logging.getLogger("toursafe.ml.dataset_registry")


class DatasetRegistryService:
    """
    Manages persistent dataset catalog in MongoDB.
    """

    async def init_indexes(self):
        try:
            db = db_core.get_database()
            await db.ml_datasets.create_index("dataset_version", unique=True)
            await db.ml_datasets.create_index("status")
            await db.ml_datasets.create_index("created_at")
        except Exception as e:
            logger.warning(f"Could not initialize ml_datasets indexes: {e}")

    async def register_dataset(self, entry: DatasetRegistryEntry) -> bool:
        db = db_core.get_database()
        doc = entry.model_dump()
        try:
            await db.ml_datasets.insert_one(doc)
            logger.info(f"Registered new dataset version: {entry.dataset_version}")
            return True
        except DuplicateKeyError:
            logger.warning(f"Dataset version {entry.dataset_version} is already registered and immutable")
            return False
        except Exception as e:
            logger.error(f"Failed to persist dataset registry entry: {e}")
            return False

    async def get_dataset(self, dataset_version: str) -> Optional[DatasetRegistryEntry]:
        db = db_core.get_database()
        doc = await db.ml_datasets.find_one({"dataset_version": dataset_version})
        if not doc:
            return None
        doc.pop("_id", None)
        return DatasetRegistryEntry.model_validate(doc)

    async def list_datasets(
        self,
        status: Optional[DatasetStatus] = None,
        limit: int = 50,
    ) -> List[DatasetRegistryEntry]:
        db = db_core.get_database()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value

        cursor = db.ml_datasets.find(query).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                results.append(DatasetRegistryEntry.model_validate(doc))
            except Exception as e:
                logger.error(f"Error parsing dataset document: {e}")
        return results

    async def update_status(self, dataset_version: str, status: DatasetStatus) -> bool:
        db = db_core.get_database()
        res = await db.ml_datasets.update_one(
            {"dataset_version": dataset_version},
            {"$set": {"status": status.value}},
        )
        return res.modified_count > 0


dataset_registry = DatasetRegistryService()
