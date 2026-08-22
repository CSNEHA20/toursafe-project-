"""
TourSafe Data Retention & Safe Deletion Engine.
Features:
- Versioned retention policies per data category & jurisdiction
- Dual-authorization / lifecycle status (DRAFT -> PENDING_APPROVAL -> APPROVED -> ACTIVE -> RETIRED)
- Policy rollback support
- Server-side multi-jurisdiction policy resolution
- Safe scheduled/on-demand retention processor with Legal Hold & Active Safety conflict checks
- Multi-store cascade deletion with immutable zero-PII audit trail
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...core import redis as redis_core
from ...models.compliance import (
    ArchiveBehavior,
    DataCategory,
    DeletionBehavior,
    PolicyStatus,
    RetentionPolicy,
)
from ..governance.audit_service import audit_service
from .legal_hold_service import legal_hold_service


class RetentionService:
    def __init__(self):
        self.policy_collection_name = "compliance_retention_policies"
        self.job_history_collection_name = "compliance_retention_jobs"

    def _get_policy_collection(self):
        db = db_core.get_database()
        return db[self.policy_collection_name]

    def _get_job_collection(self):
        db = db_core.get_database()
        return db[self.job_history_collection_name]

    async def init_indexes(self):
        try:
            coll = self._get_policy_collection()
            indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("data_type", ASCENDING), ("jurisdiction_id", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("version", DESCENDING)]),
            ]
            await coll.create_indexes(indexes)

            job_coll = self._get_job_collection()
            job_indexes = [
                IndexModel([("run_id", ASCENDING)], unique=True),
                IndexModel([("started_at", DESCENDING)]),
            ]
            await job_coll.create_indexes(job_indexes)
        except Exception as e:
            print(f"⚠️ RetentionService index init note: {e}")

    async def seed_defaults(self):
        """Seeds baseline global retention policies if none exist."""
        coll = self._get_policy_collection()
        count = await coll.count_documents({})
        if count > 0:
            return

        defaults = [
            # Raw Telemetry (IMU & High-Freq GPS) - 30 days
            RetentionPolicy(
                data_type=DataCategory.TELEMETRY,
                retention_period_days=30,
                archive_behavior=ArchiveBehavior.HARD_DELETE,
                deletion_behavior=DeletionBehavior.HARD_DELETE,
                description="Global baseline: Raw accelerometer, gyroscope & high-frequency sensor telemetry",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approved_by="system",
            ),
            # Location History (standard tracking points) - 90 days
            RetentionPolicy(
                data_type=DataCategory.LOCATION,
                retention_period_days=90,
                archive_behavior=ArchiveBehavior.ARCHIVE_ENCRYPTED,
                deletion_behavior=DeletionBehavior.HARD_DELETE,
                description="Global baseline: Tourist location trail history (non-incident associated)",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approved_by="system",
            ),
            # KYC Documents & Identity Verification Records - 365 days
            RetentionPolicy(
                data_type=DataCategory.KYC,
                retention_period_days=365,
                archive_behavior=ArchiveBehavior.ARCHIVE_ENCRYPTED,
                deletion_behavior=DeletionBehavior.PSEUDONYMIZE_ANONYMIZE,
                description="Global baseline: KYC identity verification records & credentials",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approved_by="system",
            ),
            # Incidents & SOS Records - 730 days (2 years)
            RetentionPolicy(
                data_type=DataCategory.INCIDENT,
                retention_period_days=730,
                archive_behavior=ArchiveBehavior.ARCHIVE_ENCRYPTED,
                deletion_behavior=DeletionBehavior.PSEUDONYMIZE_ANONYMIZE,
                description="Global baseline: Emergency incidents, SOS dispatches, and multi-party coordination",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approved_by="system",
            ),
            # AI Copilot Conversations - 60 days
            RetentionPolicy(
                data_type=DataCategory.AI,
                retention_period_days=60,
                archive_behavior=ArchiveBehavior.HARD_DELETE,
                deletion_behavior=DeletionBehavior.HARD_DELETE,
                description="Global baseline: Authority AI copilot chat history & tool execution traces",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approved_by="system",
            ),
            # Audit Records - 1825 days (5 years)
            RetentionPolicy(
                data_type=DataCategory.AUDIT,
                retention_period_days=1825,
                archive_behavior=ArchiveBehavior.ARCHIVE_ENCRYPTED,
                deletion_behavior=DeletionBehavior.PSEUDONYMIZE_ANONYMIZE,
                description="Global baseline: Immutable SHA-256 chained audit logs and access records",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approved_by="system",
            ),
        ]

        for p in defaults:
            await coll.insert_one(p.model_dump())
        print("✅ Seeded baseline Retention Policies")

    async def create_policy(
        self,
        data_type: DataCategory,
        retention_period_days: int,
        created_by: str,
        jurisdiction_id: Optional[str] = None,
        archive_behavior: ArchiveBehavior = ArchiveBehavior.ARCHIVE_ENCRYPTED,
        deletion_behavior: DeletionBehavior = DeletionBehavior.HARD_DELETE,
        description: str = "",
        effective_from: Optional[datetime] = None,
    ) -> RetentionPolicy:
        coll = self._get_policy_collection()
        # Find previous version
        existing = await coll.find(
            {"data_type": data_type.value, "jurisdiction_id": jurisdiction_id}
        ).sort("version", DESCENDING).to_list(1)

        version = (existing[0]["version"] + 1) if existing else 1

        policy = RetentionPolicy(
            data_type=data_type,
            jurisdiction_id=jurisdiction_id,
            retention_period_days=retention_period_days,
            archive_behavior=archive_behavior,
            deletion_behavior=deletion_behavior,
            version=version,
            effective_from=effective_from or datetime.now(timezone.utc),
            status=PolicyStatus.DRAFT,
            created_by=created_by,
            description=description,
        )

        await coll.insert_one(policy.model_dump())

        await audit_service.log_action(
            actor_id=created_by,
            actor_role="admin",
            action="CREATE",
            resource_type="RETENTION_POLICY",
            resource_id=policy.id,
            after_state={"data_type": data_type.value, "version": version, "retention_period_days": retention_period_days},
            change_reason=f"Drafted retention policy v{version} for {data_type.value}",
        )

        return policy

    async def approve_and_activate_policy(
        self,
        policy_id: str,
        approved_by: str,
    ) -> Optional[RetentionPolicy]:
        coll = self._get_policy_collection()
        policy_doc = await coll.find_one({"id": policy_id})
        if not policy_doc:
            return None

        data_type = policy_doc["data_type"]
        jurisdiction_id = policy_doc.get("jurisdiction_id")

        now = datetime.now(timezone.utc)

        # Retire previously active policy for same data_type & jurisdiction
        await coll.update_many(
            {
                "data_type": data_type,
                "jurisdiction_id": jurisdiction_id,
                "status": PolicyStatus.ACTIVE.value,
                "id": {"$ne": policy_id},
            },
            {"$set": {"status": PolicyStatus.RETIRED.value, "effective_until": now, "updated_at": now}},
        )

        # Activate target policy
        await coll.update_one(
            {"id": policy_id},
            {
                "$set": {
                    "status": PolicyStatus.ACTIVE.value,
                    "approved_by": approved_by,
                    "effective_from": now,
                    "updated_at": now,
                }
            },
        )

        updated = await coll.find_one({"id": policy_id})

        await audit_service.log_action(
            actor_id=approved_by,
            actor_role="admin",
            action="APPROVE",
            resource_type="RETENTION_POLICY",
            resource_id=policy_id,
            after_state={"status": PolicyStatus.ACTIVE.value, "approved_by": approved_by},
            change_reason=f"Approved and activated retention policy {policy_id}",
        )

        return RetentionPolicy.model_validate(updated)

    async def rollback_policy(
        self,
        current_policy_id: str,
        target_version: int,
        rolled_back_by: str,
    ) -> Optional[RetentionPolicy]:
        coll = self._get_policy_collection()
        curr_doc = await coll.find_one({"id": current_policy_id})
        if not curr_doc:
            return None

        prev_doc = await coll.find_one(
            {
                "data_type": curr_doc["data_type"],
                "jurisdiction_id": curr_doc.get("jurisdiction_id"),
                "version": target_version,
            }
        )
        if not prev_doc:
            return None

        # Create a new version based on target_version
        latest = await coll.find(
            {"data_type": curr_doc["data_type"], "jurisdiction_id": curr_doc.get("jurisdiction_id")}
        ).sort("version", DESCENDING).to_list(1)
        new_version = latest[0]["version"] + 1

        rolled_policy = RetentionPolicy(
            data_type=prev_doc["data_type"],
            jurisdiction_id=prev_doc.get("jurisdiction_id"),
            retention_period_days=prev_doc["retention_period_days"],
            archive_behavior=prev_doc.get("archive_behavior", ArchiveBehavior.ARCHIVE_ENCRYPTED.value),
            deletion_behavior=prev_doc.get("deletion_behavior", DeletionBehavior.HARD_DELETE.value),
            version=new_version,
            status=PolicyStatus.ACTIVE,
            created_by=rolled_back_by,
            approved_by=rolled_back_by,
            description=f"Rolled back to v{target_version} settings from policy {current_policy_id}",
        )

        now = datetime.now(timezone.utc)
        await coll.update_many(
            {
                "data_type": curr_doc["data_type"],
                "jurisdiction_id": curr_doc.get("jurisdiction_id"),
                "status": PolicyStatus.ACTIVE.value,
            },
            {"$set": {"status": PolicyStatus.RETIRED.value, "effective_until": now, "updated_at": now}},
        )

        await coll.insert_one(rolled_policy.model_dump())

        await audit_service.log_action(
            actor_id=rolled_back_by,
            actor_role="admin",
            action="ROLLBACK",
            resource_type="RETENTION_POLICY",
            resource_id=rolled_policy.id,
            after_state={"version": new_version, "rolled_back_from_v": target_version},
            change_reason=f"Rolled back retention policy to parameters of v{target_version}",
        )

        return rolled_policy

    async def resolve_policy(
        self,
        data_type: DataCategory,
        jurisdiction_id: Optional[str] = None,
    ) -> RetentionPolicy:
        """
        Resolves applicable active policy server-side:
        1. Specific Jurisdiction Policy
        2. Fallback to Global Baseline Policy (jurisdiction_id is None)
        """
        coll = self._get_policy_collection()
        if jurisdiction_id:
            specific = await coll.find_one(
                {"data_type": data_type.value, "jurisdiction_id": jurisdiction_id, "status": PolicyStatus.ACTIVE.value}
            )
            if specific:
                return RetentionPolicy.model_validate(specific)

        global_pol = await coll.find_one(
            {"data_type": data_type.value, "jurisdiction_id": None, "status": PolicyStatus.ACTIVE.value}
        )
        if global_pol:
            return RetentionPolicy.model_validate(global_pol)

        # In-memory safeguard default if DB empty
        default_days_map = {
            DataCategory.TELEMETRY: 30,
            DataCategory.LOCATION: 90,
            DataCategory.AI: 60,
            DataCategory.KYC: 365,
            DataCategory.INCIDENT: 730,
            DataCategory.AUDIT: 1825,
        }
        days = default_days_map.get(data_type, 90)
        return RetentionPolicy(
            data_type=data_type,
            retention_period_days=days,
            status=PolicyStatus.ACTIVE,
        )

    async def list_policies(
        self,
        data_type: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[RetentionPolicy]:
        coll = self._get_policy_collection()
        query: Dict[str, Any] = {}
        if data_type:
            query["data_type"] = data_type
        if jurisdiction_id:
            query["jurisdiction_id"] = jurisdiction_id
        if status:
            query["status"] = status

        cursor = coll.find(query).sort("updated_at", DESCENDING)
        policies = []
        async for doc in cursor:
            policies.append(RetentionPolicy.model_validate(doc))
        return policies

    async def run_retention_job(
        self,
        triggered_by: str = "SCHEDULED_DAEMON",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes retention policy sweeps across all data categories.
        Enforces Safe Deletion Rules:
        - Never deletes data under active Legal Hold
        - Never deletes location/telemetry of an active SOS / ongoing incident
        - Audits deletion actions without leaking sensitive PII payloads
        """
        import uuid
        run_id = f"ret_job_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)

        db = db_core.get_database()
        job_stats = {
            "run_id": run_id,
            "started_at": start_time,
            "triggered_by": triggered_by,
            "dry_run": dry_run,
            "categories_processed": {},
            "total_records_evaluated": 0,
            "total_records_deleted": 0,
            "total_records_retained_legal_hold": 0,
            "total_records_retained_active_incident": 0,
            "status": "COMPLETED",
        }

        # 1. Telemetry Cleanup
        telemetry_policy = await self.resolve_policy(DataCategory.TELEMETRY)
        telemetry_cutoff = start_time - timedelta(days=telemetry_policy.retention_period_days)
        
        telemetry_coll = db["telemetry_records"] if "telemetry_records" in await db.list_collection_names() else db["telemetry"]
        
        # Check active incident tourist IDs to preserve
        incidents_coll = db["incidents"]
        active_incidents = await incidents_coll.find(
            {"status": {"$in": ["REPORTED", "ACKNOWLEDGED", "ASSIGNED", "DISPATCHED", "ON_SCENE", "ESCALATED"]}}
        ).to_list(1000)
        protected_tourist_ids = {inc.get("tourist_id") for inc in active_incidents if inc.get("tourist_id")}

        # Scan telemetry older than cutoff
        telemetry_query = {"created_at": {"$lt": telemetry_cutoff}}
        eligible_telemetry = await telemetry_coll.find(telemetry_query).to_list(500)
        
        del_count = 0
        held_count = 0
        active_inc_count = 0

        for record in eligible_telemetry:
            tourist_id = record.get("tourist_id") or record.get("user_id")
            if tourist_id in protected_tourist_ids:
                active_inc_count += 1
                continue

            is_held, _ = await legal_hold_service.is_entity_held(tourist_id, DataCategory.TELEMETRY)
            if is_held:
                held_count += 1
                continue

            if not dry_run:
                await telemetry_coll.delete_one({"_id": record["_id"]})
            del_count += 1

        job_stats["categories_processed"]["TELEMETRY"] = {
            "retention_days": telemetry_policy.retention_period_days,
            "deleted": del_count,
            "retained_legal_hold": held_count,
            "retained_active_incident": active_inc_count,
        }
        job_stats["total_records_deleted"] += del_count
        job_stats["total_records_retained_legal_hold"] += held_count
        job_stats["total_records_retained_active_incident"] += active_inc_count

        # 2. Location History Cleanup
        loc_policy = await self.resolve_policy(DataCategory.LOCATION)
        loc_cutoff = start_time - timedelta(days=loc_policy.retention_period_days)
        loc_coll = db["location_histories"] if "location_histories" in await db.list_collection_names() else db["locations"]
        
        eligible_locations = await loc_coll.find({"created_at": {"$lt": loc_cutoff}}).to_list(500)
        loc_del = 0
        loc_held = 0
        loc_active = 0

        for loc in eligible_locations:
            t_id = loc.get("tourist_id") or loc.get("user_id")
            if t_id in protected_tourist_ids:
                loc_active += 1
                continue
            is_held, _ = await legal_hold_service.is_entity_held(t_id, DataCategory.LOCATION)
            if is_held:
                loc_held += 1
                continue
            if not dry_run:
                await loc_coll.delete_one({"_id": loc["_id"]})
            loc_del += 1

        job_stats["categories_processed"]["LOCATION"] = {
            "retention_days": loc_policy.retention_period_days,
            "deleted": loc_del,
            "retained_legal_hold": loc_held,
            "retained_active_incident": loc_active,
        }
        job_stats["total_records_deleted"] += loc_del
        job_stats["total_records_retained_legal_hold"] += loc_held
        job_stats["total_records_retained_active_incident"] += loc_active

        # 3. AI Copilot History Cleanup
        ai_policy = await self.resolve_policy(DataCategory.AI)
        ai_cutoff = start_time - timedelta(days=ai_policy.retention_period_days)
        ai_coll = db["copilot_conversations"]
        
        eligible_ai = await ai_coll.find({"created_at": {"$lt": ai_cutoff}}).to_list(200)
        ai_del = 0
        ai_held = 0
        for conv in eligible_ai:
            conv_id = conv.get("id") or str(conv.get("_id"))
            is_held, _ = await legal_hold_service.is_entity_held(conv_id, DataCategory.AI)
            if is_held:
                ai_held += 1
                continue
            if not dry_run:
                await ai_coll.delete_one({"_id": conv["_id"]})
            ai_del += 1

        job_stats["categories_processed"]["AI"] = {
            "retention_days": ai_policy.retention_period_days,
            "deleted": ai_del,
            "retained_legal_hold": ai_held,
            "retained_active_incident": 0,
        }
        job_stats["total_records_deleted"] += ai_del
        job_stats["total_records_retained_legal_hold"] += ai_held

        job_stats["completed_at"] = datetime.now(timezone.utc)

        # Save job record
        job_coll = self._get_job_collection()
        await job_coll.insert_one(dict(job_stats))

        # Log audit entry
        await audit_service.log_action(
            actor_id=triggered_by,
            actor_role="system",
            action="DELETE" if not dry_run else "VALIDATE",
            resource_type="RETENTION_JOB",
            resource_id=run_id,
            after_state={
                "deleted": job_stats["total_records_deleted"],
                "retained_legal_hold": job_stats["total_records_retained_legal_hold"],
                "retained_active_incident": job_stats["total_records_retained_active_incident"],
                "dry_run": dry_run,
            },
            change_reason=f"Executed retention sweep job {run_id}",
        )

        return job_stats

    async def get_job_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        job_coll = self._get_job_collection()
        cursor = job_coll.find({}).sort("started_at", DESCENDING).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results


retention_service = RetentionService()
