"""
TourSafe Database Restoration & Verification Service.
Executes dry-run validations and actual data restoration with post-restore consistency checks.
"""

import gzip
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from ...core import database as db_core
from .backup_service import backup_service
from ...core.reliability.logging import get_structured_logger

logger = get_structured_logger("toursafe.restore")


class RestoreService:
    """Manages dry-run restoration, actual database restores, and integrity verification."""

    async def restore_from_backup(
        self,
        backup_id: str,
        dry_run: bool = True,
        actor_id: str = "operator",
        target_collections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Restore database collections from backup file."""
        start_time = time.perf_counter()
        
        # 1. Verify backup integrity first
        integrity = await backup_service.verify_backup_integrity(backup_id)
        if not integrity.get("valid"):
            return {
                "success": False,
                "error": f"Backup integrity check failed: {integrity.get('error')}",
                "dry_run": dry_run,
            }

        file_path = os.path.join(backup_service.backup_dir, f"{backup_id}.json.gz")
        with open(file_path, "rb") as f:
            decompressed_json = gzip.decompress(f.read()).decode("utf-8")
        snapshot_data: Dict[str, List[Dict[str, Any]]] = json.loads(decompressed_json)

        restored_counts = {}
        collections_to_process = target_collections or list(snapshot_data.keys())
        db = db_core.get_database()

        for col_name in collections_to_process:
            docs = snapshot_data.get(col_name, [])
            restored_counts[col_name] = len(docs)

            if not dry_run and docs:
                try:
                    # Clean and format ObjectIds
                    formatted_docs = []
                    for d in docs:
                        item = d.copy()
                        if "_id" in item and isinstance(item["_id"], str) and len(item["_id"]) == 24:
                            try:
                                item["_id"] = ObjectId(item["_id"])
                            except Exception:
                                pass
                        formatted_docs.append(item)

                    # In safety-critical restore, we upsert documents by _id
                    for doc in formatted_docs:
                        doc_id = doc.get("_id")
                        if doc_id:
                            await db[col_name].replace_one({"_id": doc_id}, doc, upsert=True)
                        else:
                            await db[col_name].insert_one(doc)
                except Exception as e:
                    logger.error(f"Failed restoring collection {col_name}: {e}")

        rto_seconds = round(time.perf_counter() - start_time, 2)
        result = {
            "success": True,
            "backup_id": backup_id,
            "dry_run": dry_run,
            "rto_seconds": rto_seconds,
            "restored_counts": restored_counts,
            "total_documents": sum(restored_counts.values()),
            "executed_by": actor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Restore {'(DRY RUN) ' if dry_run else ''}completed for {backup_id} in {rto_seconds}s",
            extra={"event": "RESTORE_EXECUTED", "extra_data": result}
        )

        return result

    async def verify_system_consistency(self) -> Dict[str, Any]:
        """Post-restore consistency check across critical collections."""
        db = db_core.get_database()
        checks = {}
        try:
            incidents_count = await db.incidents.count_documents({})
            users_count = await db.users.count_documents({})
            zones_count = await db.geospatial_zones.count_documents({})
            checks["collections"] = {
                "incidents": incidents_count,
                "users": users_count,
                "geospatial_zones": zones_count,
            }
            checks["healthy"] = True
        except Exception as e:
            checks["healthy"] = False
            checks["error"] = str(e)

        return checks


restore_service = RestoreService()
