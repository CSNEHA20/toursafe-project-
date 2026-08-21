import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pymongo.errors import DuplicateKeyError
from ...core.config import settings
from ...core import database as db_core
from ...schemas.telemetry import TelemetrySample, TelemetryWindow

logger = logging.getLogger("toursafe.telemetry.persistence")


class TelemetryPersistenceManager:
    """
    Manages durable MongoDB persistence for telemetry samples and generated windows.
    Applies idempotency protection, indexing efficiency, and retention management.
    """

    async def persist_sample(self, sample: TelemetrySample) -> bool:
        """
        Persists a single validated telemetry sample to the telemetry_samples collection.
        Handles duplicate packet IDs gracefully (idempotent).
        """
        db = db_core.get_database()
        doc = sample.model_dump()

        # Add GeoJSON point for geospatial indexing if GPS is available
        if sample.gps:
            doc["location"] = {
                "type": "Point",
                "coordinates": [sample.gps.longitude, sample.gps.latitude],
            }

        try:
            await db.telemetry_samples.insert_one(doc)
            return True
        except DuplicateKeyError:
            logger.debug("Idempotency match: sample %s already persisted", sample.packet_id)
            return False
        except Exception as e:
            logger.error("Failed to persist telemetry sample: %s", e)
            return False

    async def persist_samples_batch(self, samples: List[TelemetrySample]) -> int:
        """
        Batch inserts multiple telemetry samples efficiently with ordered=False (skips duplicates).
        """
        if not samples:
            return 0

        db = db_core.get_database()
        docs = []
        for s in samples:
            d = s.model_dump()
            if s.gps:
                d["location"] = {
                    "type": "Point",
                    "coordinates": [s.gps.longitude, s.gps.latitude],
                }
            docs.append(d)

        try:
            res = await db.telemetry_samples.insert_many(docs, ordered=False)
            return len(res.inserted_ids)
        except Exception as e:
            # When ordered=False, DuplicateKeyError still inserts non-duplicates
            logger.debug("Batch insert note (some duplicates skipped): %s", e)
            return len(docs)

    async def persist_window(self, window: TelemetryWindow) -> bool:
        """
        Persists a generated 3-second TelemetryWindow for future AI / downstream consumption.
        """
        db = db_core.get_database()
        doc = window.model_dump()
        try:
            await db.telemetry_windows.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False
        except Exception as e:
            logger.error("Failed to persist telemetry window: %s", e)
            return False

    async def query_session_samples(
        self,
        session_id: str,
        limit: int = 500,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieves raw samples for a session."""
        db = db_core.get_database()
        cursor = (
            db.telemetry_samples.find({"session_id": session_id})
            .sort("sequence_number", 1)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def query_session_windows(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieves recent generated windows for a session."""
        db = db_core.get_database()
        cursor = (
            db.telemetry_windows.find({"session_id": session_id})
            .sort("window_start", -1)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def apply_retention_policy(self) -> int:
        """
        Deletes telemetry records older than TELEMETRY_RETENTION_DAYS.
        """
        days = settings.telemetry_retention_days
        if days <= 0:
            return 0

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        db = db_core.get_database()
        try:
            res_samples = await db.telemetry_samples.delete_many({"timestamp": {"$lt": cutoff}})
            res_windows = await db.telemetry_windows.delete_many({"window_start": {"$lt": cutoff}})
            deleted = res_samples.deleted_count + res_windows.deleted_count
            logger.info("Retention policy purged %d records older than %d days", deleted, days)
            return deleted
        except Exception as e:
            logger.warning("Retention policy cleanup error: %s", e)
            return 0


telemetry_persistence = TelemetryPersistenceManager()
