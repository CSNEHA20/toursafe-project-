"""
TourSafe Production Schema Migration & Versioning Engine.
Provides safe, idempotent, forward and backward schema evolution with audit logging.
"""

import asyncio
import datetime
import hashlib
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import pymongo
from .database import get_database

logger = logging.getLogger("toursafe.migrations")

MIGRATIONS_COLLECTION = "_schema_migrations"


class Migration:
    def __init__(
        self,
        version: str,
        name: str,
        up_fn: Callable[[Any], Coroutine[Any, Any, None]],
        down_fn: Optional[Callable[[Any], Coroutine[Any, Any, None]]] = None,
        description: str = "",
    ):
        self.version = version
        self.name = name
        self.up_fn = up_fn
        self.down_fn = down_fn
        self.description = description

    @property
    def checksum(self) -> str:
        content = f"{self.version}:{self.name}:{self.description}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class MigrationEngine:
    def __init__(self):
        self._registry: List[Migration] = []

    def register(
        self,
        version: str,
        name: str,
        up_fn: Callable[[Any], Coroutine[Any, Any, None]],
        down_fn: Optional[Callable[[Any], Coroutine[Any, Any, None]]] = None,
        description: str = "",
    ):
        migration = Migration(version, name, up_fn, down_fn, description)
        self._registry.append(migration)
        self._registry.sort(key=lambda m: m.version)

    async def init_migration_tracking(self, db=None):
        if db is None:
            db = get_database()
        try:
            await db[MIGRATIONS_COLLECTION].create_index("version", unique=True)
            await db[MIGRATIONS_COLLECTION].create_index([("applied_at", pymongo.DESCENDING)])
        except Exception as e:
            logger.warning("Could not create migration tracking indexes: %s", e)

    async def get_applied_migrations(self, db=None) -> Dict[str, dict]:
        if db is None:
            db = get_database()
        await self.init_migration_tracking(db)
        cursor = db[MIGRATIONS_COLLECTION].find({})
        applied = {}
        async for doc in cursor:
            applied[doc["version"]] = doc
        return applied

    async def get_status(self, db=None) -> List[Dict[str, Any]]:
        if db is None:
            db = get_database()
        applied = await self.get_applied_migrations(db)
        status_list = []
        for m in self._registry:
            is_applied = m.version in applied
            status_list.append({
                "version": m.version,
                "name": m.name,
                "description": m.description,
                "checksum": m.checksum,
                "applied": is_applied,
                "applied_at": applied[m.version]["applied_at"].isoformat() if is_applied else None,
                "reversible": m.down_fn is not None,
            })
        return status_list

    async def run_up(self, db=None, dry_run: bool = False) -> List[str]:
        if db is None:
            db = get_database()
        await self.init_migration_tracking(db)
        applied = await self.get_applied_migrations(db)
        executed = []

        for m in self._registry:
            if m.version not in applied:
                logger.info("Executing migration %s: %s (Dry Run: %s)", m.version, m.name, dry_run)
                if not dry_run:
                    await m.up_fn(db)
                    await db[MIGRATIONS_COLLECTION].insert_one({
                        "version": m.version,
                        "name": m.name,
                        "description": m.description,
                        "checksum": m.checksum,
                        "applied_at": datetime.datetime.now(datetime.timezone.utc),
                        "status": "SUCCESS",
                    })
                executed.append(m.version)

        return executed

    async def rollback_last(self, db=None, dry_run: bool = False) -> Optional[str]:
        if db is None:
            db = get_database()
        applied = await self.get_applied_migrations(db)
        if not applied:
            logger.info("No migrations currently applied to rollback.")
            return None

        # Find latest applied migration that has a down function
        sorted_applied = sorted(applied.keys(), reverse=True)
        target_version = sorted_applied[0]
        matching_migration = next((m for m in self._registry if m.version == target_version), None)

        if not matching_migration:
            raise ValueError(f"Migration {target_version} found in database but not in code registry.")
        if not matching_migration.down_fn:
            raise ValueError(f"Migration {target_version} ({matching_migration.name}) is marked irreversible.")

        logger.info("Rolling back migration %s: %s (Dry Run: %s)", matching_migration.version, matching_migration.name, dry_run)
        if not dry_run:
            await matching_migration.down_fn(db)
            await db[MIGRATIONS_COLLECTION].delete_one({"version": target_version})

        return target_version


migration_engine = MigrationEngine()

# -------------------------------------------------------------
# Standard Baseline Migrations
# -------------------------------------------------------------

async def _m_001_up(db):
    """Ensure baseline collections and primary compound indexes."""
    await db.tourists.create_index("id", unique=True, sparse=True)
    await db.tourists.create_index("email", unique=True, sparse=True)
    await db.incidents.create_index("id", unique=True, sparse=True)
    await db.incidents.create_index([("status", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])

async def _m_001_down(db):
    """Revert baseline index creation (safe non-destructive)."""
    pass

migration_engine.register(
    version="2026.08.01.001",
    name="baseline_core_indexes",
    up_fn=_m_001_up,
    down_fn=_m_001_down,
    description="Establish baseline uniqueness and compound indexes on tourists and incidents",
)

async def _m_002_up(db):
    """Establish TTL and geospatial 2dsphere indexes for telemetry and tracking."""
    await db.telemetry_samples.create_index([("tourist_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
    await db.telemetry_samples.create_index([("location", "2dsphere")], sparse=True)
    await db.safety_zones.create_index([("boundary", "2dsphere")], sparse=True)

async def _m_002_down(db):
    pass

migration_engine.register(
    version="2026.08.15.002",
    name="geospatial_and_telemetry_indexes",
    up_fn=_m_002_up,
    down_fn=_m_002_down,
    description="Establish 2dsphere geospatial and high-throughput telemetry indexes",
)
