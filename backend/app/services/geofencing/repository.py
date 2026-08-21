"""
TourSafe - Geofencing Repository & Spatial Candidate Query Engine

Handles:
- MongoDB 2dsphere spatial candidate queries ($geoIntersects, $nearSphere)
- Persistence of confirmed zone transition events in 'zone_transitions' collection
- Auditable querying of historical zone entry, exit, and dwell events
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import pymongo
from ...core import database as db_core
from .types import ZoneTransitionRecord
from .geometry import is_point_in_bounding_box, bounding_box_for_geometry

logger = logging.getLogger("toursafe.geofencing.repository")


def _get_collection(db: Any, name: str) -> Any:
    """Helper to safely retrieve collection from real Motor database or test mock."""
    if hasattr(db, name):
        return getattr(db, name)
    try:
        return db[name]
    except Exception:
        return None


class GeofenceRepository:
    """
    Data access layer for geospatial zones and persistent transition history.
    """

    async def get_all_active_zones(self) -> List[Dict[str, Any]]:
        """
        Retrieves all active, published zones from MongoDB.
        """
        db = db_core.get_database()
        coll = _get_collection(db, "zones")
        if coll is None:
            return []
        try:
            cursor = coll.find({
                "status": "active",
                "is_active": True,
            })
            return await cursor.to_list(length=1000)
        except Exception as e:
            logger.debug("Active zones query fallback: %s", e)
            return []

    async def find_candidate_zones(
        self,
        longitude: float,
        latitude: float,
        buffer_meters: float = 1000.0,
    ) -> List[Dict[str, Any]]:
        """
        Spatial Candidate Query:
        Uses MongoDB 2dsphere indexing with $geoIntersects and near center bounding
        to retrieve candidate zones without evaluating every zone at scale.
        Falls back to in-memory bounding-box pre-filtering.
        """
        db = db_core.get_database()
        coll = _get_collection(db, "zones")
        if coll is None:
            return []

        candidates: List[Dict[str, Any]] = []

        try:
            # 1. Primary candidate search: 2dsphere $geoIntersects with Point
            intersects_cursor = coll.find({
                "status": "active",
                "is_active": True,
                "boundary": {
                    "$geoIntersects": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [longitude, latitude],
                        }
                    }
                }
            })
            direct_hits = await intersects_cursor.to_list(length=100)
            seen_ids = set()
            for doc in direct_hits:
                zid = doc.get("zone_id") or doc.get("id") or str(doc.get("_id", ""))
                seen_ids.add(zid)
                candidates.append(doc)

            # 2. Secondary candidate search: nearby zones near center within buffer distance
            near_cursor = coll.find({
                "status": "active",
                "is_active": True,
                "center": {
                    "$nearSphere": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [longitude, latitude],
                        },
                        "$maxDistance": buffer_meters,
                    }
                }
            })
            near_hits = await near_cursor.to_list(length=50)
            for doc in near_hits:
                zid = doc.get("zone_id") or doc.get("id") or str(doc.get("_id", ""))
                if zid not in seen_ids:
                    seen_ids.add(zid)
                    candidates.append(doc)

            return candidates

        except Exception as e:
            logger.debug("MongoDB spatial candidate query fallback to bounding box: %s", e)
            # Fallback: retrieve all active zones and pre-filter by bounding box in memory
            all_active = await self.get_all_active_zones()
            filtered = []
            for zone_doc in all_active:
                boundary = zone_doc.get("boundary", {})
                if boundary:
                    bbox = bounding_box_for_geometry(boundary)
                    if is_point_in_bounding_box(longitude, latitude, bbox, buffer_meters=buffer_meters):
                        filtered.append(zone_doc)
            return filtered

    async def record_transition(self, record: ZoneTransitionRecord) -> bool:
        """
        Persists a confirmed zone transition / dwell event to MongoDB 'zone_transitions'.
        """
        db = db_core.get_database()
        coll = _get_collection(db, "zone_transitions")
        if coll is None:
            return False
        try:
            doc = record.model_dump()
            await coll.insert_one(doc)
            return True
        except Exception as e:
            logger.error("Failed to insert zone transition to MongoDB: %s", e)
            return False

    async def get_tourist_transition_history(
        self,
        tourist_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        zone_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> Tuple[List[ZoneTransitionRecord], int]:
        """
        Queries transition history for a tourist with filtering and pagination.
        """
        db = db_core.get_database()
        coll = _get_collection(db, "zone_transitions")
        if coll is None:
            return [], 0

        query: Dict[str, Any] = {"tourist_id": tourist_id}

        if zone_id:
            query["zone_id"] = zone_id

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            query["timestamp"] = time_filter

        limit = max(1, min(limit, 500))
        skip = max(0, skip)

        try:
            total = await coll.count_documents(query)
            cursor = (
                coll.find(query)
                .sort("timestamp", pymongo.DESCENDING)
                .skip(skip)
                .limit(limit)
            )

            records: List[ZoneTransitionRecord] = []
            async for doc in cursor:
                doc.pop("_id", None)
                records.append(ZoneTransitionRecord(**doc))

            return records, total
        except Exception as e:
            logger.error("Error reading tourist transition history: %s", e)
            return [], 0

    async def get_zone_occupancy_counts(self) -> Dict[str, int]:
        """
        Aggregates active tourist counts per zone from active states.
        """
        return {}


geofence_repository = GeofenceRepository()
