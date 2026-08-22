"""
TourSafe Immutable Audit Logging Service.
Guarantees append-only, tamper-evident audit logging for all administrative,
governance, policy configuration, responder assignment, and manual override actions.
Implements SHA-256 cryptographic hash chaining across sequential audit entries.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.governance import AuditAction, ImmutableAuditRecord
from ...schemas.governance import AuditPaginatedResponse, AuditQueryFilter, AuditRecordResponse


class AuditService:
    def __init__(self):
        self.collection_name = "governance_audit_logs"

    def _get_collection(self):
        db = db_core.get_database()
        return db[self.collection_name]

    async def init_indexes(self):
        """Initializes database indexes for audit querying and performance."""
        try:
            coll = self._get_collection()
            indexes = [
                IndexModel([("timestamp", DESCENDING)]),
                IndexModel([("actor_id", ASCENDING), ("timestamp", DESCENDING)]),
                IndexModel([("resource_type", ASCENDING), ("resource_id", ASCENDING)]),
                IndexModel([("action", ASCENDING)]),
                IndexModel([("jurisdiction_id", ASCENDING)]),
                IndexModel([("audit_id", ASCENDING)], unique=True),
            ]
            await coll.create_indexes(indexes)
        except Exception as e:
            print(f"⚠️ AuditService index initialization note: {e}")

    async def log_action(
        self,
        actor_id: str,
        actor_role: str,
        action: AuditAction | str,
        resource_type: str,
        resource_id: str,
        actor_name: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ImmutableAuditRecord:
        """
        Appends an immutable audit record to the governance audit log.
        Fetches the previous entry's integrity hash and chains it cryptographically.
        """
        coll = self._get_collection()
        previous_hash = "GENESIS_HASH"
        try:
            latest = await coll.find_one({}, sort=[("timestamp", DESCENDING), ("_id", DESCENDING)])
            if latest and latest.get("integrity_hash"):
                previous_hash = latest["integrity_hash"]
        except Exception:
            pass

        record = ImmutableAuditRecord(
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            action=action if isinstance(action, AuditAction) else AuditAction(action),
            resource_type=resource_type,
            resource_id=resource_id,
            jurisdiction_id=jurisdiction_id,
            before_state=before_state,
            after_state=after_state,
            change_reason=change_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            previous_hash=previous_hash,
            timestamp=datetime.now(timezone.utc),
        )
        record.integrity_hash = record.compute_integrity_hash()

        doc = record.to_dict()
        await coll.insert_one(doc)
        return record

    async def verify_audit_chain(self, limit: int = 100) -> Dict[str, Any]:
        """
        Traverses audit log records in chronological order to verify cryptographic hash chaining
        and integrity. Detects tampered, modified, or omitted records.
        """
        coll = self._get_collection()
        cursor = coll.find().sort("timestamp", ASCENDING).limit(limit)
        records = await cursor.to_list(length=limit)

        if not records:
            return {"valid": True, "records_checked": 0, "status": "EMPTY_LOG"}

        expected_prev_hash = "GENESIS_HASH"
        for idx, doc in enumerate(records):
            # Check previous hash continuity
            prev_hash = doc.get("previous_hash", "GENESIS_HASH")
            if idx == 0:
                expected_prev_hash = prev_hash

            if prev_hash != expected_prev_hash:
                return {
                    "valid": False,
                    "records_checked": idx + 1,
                    "tampered_audit_id": doc.get("audit_id"),
                    "error": f"Chain broken at record {idx+1}: expected previous_hash {expected_prev_hash}, got {prev_hash}",
                }

            # Recompute hash for the record with tamper exception safety
            try:
                record_obj = ImmutableAuditRecord(
                    audit_id=doc.get("audit_id"),
                    timestamp=datetime.fromisoformat(doc.get("timestamp")) if isinstance(doc.get("timestamp"), str) else doc.get("timestamp"),
                    actor_id=doc.get("actor_id"),
                    actor_name=doc.get("actor_name"),
                    actor_role=doc.get("actor_role"),
                    action=doc.get("action"),
                    resource_type=doc.get("resource_type"),
                    resource_id=doc.get("resource_id"),
                    jurisdiction_id=doc.get("jurisdiction_id"),
                    before_state=doc.get("before_state"),
                    after_state=doc.get("after_state"),
                    change_reason=doc.get("change_reason"),
                    ip_address=doc.get("ip_address"),
                    user_agent=doc.get("user_agent"),
                    previous_hash=prev_hash,
                )
                recomputed = record_obj.compute_integrity_hash()
            except Exception as e:
                return {
                    "valid": False,
                    "records_checked": idx + 1,
                    "tampered_audit_id": doc.get("audit_id"),
                    "error": f"Tamper detected (payload schema corruption): {e}",
                }

            stored_hash = doc.get("integrity_hash")

            if recomputed != stored_hash:
                return {
                    "valid": False,
                    "records_checked": idx + 1,
                    "tampered_audit_id": doc.get("audit_id"),
                    "error": f"Tamper detected: stored integrity hash {stored_hash} does not match computed {recomputed}",
                }

            expected_prev_hash = stored_hash

        return {
            "valid": True,
            "records_checked": len(records),
            "latest_chain_hash": expected_prev_hash,
            "status": "SECURE",
        }

    async def query_logs(
        self,
        filter_params: AuditQueryFilter,
        enforce_jurisdiction_id: Optional[str] = None,
    ) -> AuditPaginatedResponse:
        """
        Queries audit logs with pagination, filtering, and optional jurisdiction isolation.
        """
        coll = self._get_collection()
        query: Dict[str, Any] = {}

        if enforce_jurisdiction_id:
            query["jurisdiction_id"] = enforce_jurisdiction_id
        elif filter_params.jurisdiction_id:
            query["jurisdiction_id"] = filter_params.jurisdiction_id

        if filter_params.actor_id:
            query["actor_id"] = filter_params.actor_id

        if filter_params.actor_role:
            query["actor_role"] = filter_params.actor_role

        if filter_params.action:
            query["action"] = (
                filter_params.action.value if hasattr(filter_params.action, "value") else str(filter_params.action)
            )

        if filter_params.resource_type:
            query["resource_type"] = filter_params.resource_type

        if filter_params.resource_id:
            query["resource_id"] = filter_params.resource_id

        if filter_params.date_from or filter_params.date_to:
            time_query = {}
            if filter_params.date_from:
                time_query["$gte"] = filter_params.date_from.isoformat()
            if filter_params.date_to:
                time_query["$lte"] = filter_params.date_to.isoformat()
            query["timestamp"] = time_query

        if filter_params.search:
            search_regex = {"$regex": filter_params.search, "$options": "i"}
            query["$or"] = [
                {"change_reason": search_regex},
                {"resource_id": search_regex},
                {"actor_name": search_regex},
            ]

        total = await coll.count_documents(query)
        skip = (filter_params.page - 1) * filter_params.limit

        cursor = coll.find(query).sort("timestamp", DESCENDING).skip(skip).limit(filter_params.limit)
        items = []
        async for doc in cursor:
            items.append(
                AuditRecordResponse(
                    audit_id=doc.get("audit_id", ""),
                    timestamp=doc.get("timestamp", ""),
                    actor_id=doc.get("actor_id", ""),
                    actor_name=doc.get("actor_name"),
                    actor_role=doc.get("actor_role", "system"),
                    action=doc.get("action", ""),
                    resource_type=doc.get("resource_type", ""),
                    resource_id=doc.get("resource_id", ""),
                    jurisdiction_id=doc.get("jurisdiction_id"),
                    before_state=doc.get("before_state"),
                    after_state=doc.get("after_state"),
                    change_reason=doc.get("change_reason"),
                    ip_address=doc.get("ip_address"),
                    previous_hash=doc.get("previous_hash"),
                    integrity_hash=doc.get("integrity_hash"),
                )
            )

        pages = max(1, (total + filter_params.limit - 1) // filter_params.limit)
        return AuditPaginatedResponse(
            items=items,
            total=total,
            page=filter_params.page,
            limit=filter_params.limit,
            pages=pages,
        )

    async def get_audit_record(self, audit_id: str) -> Optional[Dict[str, Any]]:
        coll = self._get_collection()
        return await coll.find_one({"audit_id": audit_id}, {"_id": 0})

    # Guard methods to guarantee audit immutability
    async def update_audit_record(self, *args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: Audit logs are strictly immutable and cannot be updated.",
        )

    async def delete_audit_record(self, *args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: Audit logs are strictly immutable and cannot be deleted.",
        )


audit_service = AuditService()
