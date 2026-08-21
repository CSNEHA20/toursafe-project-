"""
TourSafe Anomaly MongoDB Persistence Service.
Stores persistent anomaly episode records in the 'anomaly_events' collection,
with index management and query capabilities.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from ...core import database as db_core
from ...schemas.ml import AnomalyEpisode

logger = logging.getLogger("toursafe.ml.persistence")


class AnomalyPersistenceService:
    """
    Manages durable storage of anomaly episodes in MongoDB.
    """

    async def init_indexes(self):
        """Creates required MongoDB indexes for anomaly events."""
        try:
            db = db_core.get_database()
            collection = db["anomaly_events"]
            await collection.create_index([("anomaly_id", 1)], unique=True)
            await collection.create_index([("tourist_id", 1), ("started_at", -1)])
            await collection.create_index([("session_id", 1)])
            await collection.create_index([("status", 1)])
            await collection.create_index([("created_at", -1)])
            logger.info("Initialized MongoDB indexes for anomaly_events collection")
        except Exception as e:
            logger.debug(f"Index initialization note for anomaly_events: {e}")

    async def upsert_anomaly_episode(self, episode: AnomalyEpisode) -> bool:
        """
        Inserts or updates an anomaly episode in MongoDB.
        """
        try:
            db = db_core.get_database()
            collection = db["anomaly_events"]
            doc = episode.model_dump()
            await collection.update_one(
                {"anomaly_id": episode.anomaly_id},
                {"$set": doc},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upsert anomaly episode {episode.anomaly_id}: {e}")
            return False

    async def get_active_episodes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves active anomaly episodes from MongoDB.
        """
        try:
            db = db_core.get_database()
            collection = db["anomaly_events"]
            cursor = collection.find({"status": "active"}).sort("updated_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            for d in docs:
                if "_id" in d:
                    d["_id"] = str(d["_id"])
            return docs
        except Exception as e:
            logger.error(f"Failed to retrieve active anomaly episodes: {e}")
            return []

    async def get_historical_episodes(
        self,
        tourist_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves historical anomaly episodes from MongoDB.
        """
        try:
            db = db_core.get_database()
            collection = db["anomaly_events"]
            query: Dict[str, Any] = {}
            if tourist_id:
                query["tourist_id"] = tourist_id

            cursor = collection.find(query).sort("started_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            for d in docs:
                if "_id" in d:
                    d["_id"] = str(d["_id"])
            return docs
        except Exception as e:
            logger.error(f"Failed to retrieve historical anomaly episodes: {e}")
            return []


anomaly_persistence = AnomalyPersistenceService()
