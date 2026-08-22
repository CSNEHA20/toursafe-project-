"""
TourSafe Access Governance & Privileged Access Management (PAM) Service.
Features:
- Scheduled periodic access reviews across privileged roles & service accounts
- Inactive user and stale permission identification
- Time-bounded emergency Break-Glass access elevation with justification and audit
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.compliance import (
    AccessReview,
    AccessReviewScope,
    AccessReviewStatus,
    BreakGlassSession,
)
from ..governance.audit_service import audit_service


class AccessGovernanceService:
    def __init__(self):
        self.reviews_collection = "compliance_access_reviews"
        self.break_glass_collection = "compliance_break_glass_sessions"

    def _get_reviews_coll(self):
        db = db_core.get_database()
        return db[self.reviews_collection]

    def _get_bg_coll(self):
        db = db_core.get_database()
        return db[self.break_glass_collection]

    async def init_indexes(self):
        try:
            coll = self._get_reviews_coll()
            indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("period_end", DESCENDING)]),
            ]
            await coll.create_indexes(indexes)

            bg_coll = self._get_bg_coll()
            bg_indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("expires_at", ASCENDING)]),
            ]
            await bg_coll.create_indexes(bg_indexes)
        except Exception as e:
            print(f"⚠️ AccessGovernanceService index init note: {e}")

    async def create_access_review(
        self,
        title: str,
        scope: AccessReviewScope,
        reviewer_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> AccessReview:
        db = db_core.get_database()
        
        # Populate candidate accounts based on scope
        accounts_to_review = []
        if scope == AccessReviewScope.ADMIN_USERS:
            users = await db["users"].find({"role": "admin"}).to_list(100)
            for u in users:
                accounts_to_review.append({
                    "user_id": u.get("id"),
                    "email": u.get("email"),
                    "role": u.get("role"),
                    "is_active": u.get("is_active", True),
                    "last_login": u.get("last_login_at"),
                    "decision": "PENDING",
                })
        elif scope == AccessReviewScope.AUTHORITY_OFFICERS:
            users = await db["users"].find({"role": "authority"}).to_list(200)
            for u in users:
                accounts_to_review.append({
                    "user_id": u.get("id"),
                    "email": u.get("email"),
                    "role": u.get("role"),
                    "is_active": u.get("is_active", True),
                    "last_login": u.get("last_login_at"),
                    "decision": "PENDING",
                })
        elif scope == AccessReviewScope.RESPONDERS:
            users = await db["users"].find({"role": "responder"}).to_list(300)
            for u in users:
                accounts_to_review.append({
                    "user_id": u.get("id"),
                    "email": u.get("email"),
                    "role": u.get("role"),
                    "is_active": u.get("is_active", True),
                    "last_login": u.get("last_login_at"),
                    "decision": "PENDING",
                })
        else:  # SERVICE_ACCOUNTS
            accounts_to_review.append({
                "user_id": "svc_ml_inference",
                "email": "svc-ml@toursafe.internal",
                "role": "service_account",
                "is_active": True,
                "decision": "PENDING",
            })
            accounts_to_review.append({
                "user_id": "svc_cad_integration",
                "email": "svc-cad@toursafe.internal",
                "role": "service_account",
                "is_active": True,
                "decision": "PENDING",
            })

        review = AccessReview(
            title=title,
            scope=scope,
            reviewer_id=reviewer_id,
            period_start=period_start,
            period_end=period_end,
            status=AccessReviewStatus.SCHEDULED,
            accounts_reviewed=accounts_to_review,
        )

        coll = self._get_reviews_coll()
        await coll.insert_one(review.model_dump())

        scope_val = scope.value if hasattr(scope, "value") else str(scope)
        await audit_service.log_action(
            actor_id=reviewer_id,
            actor_role="admin",
            action="CREATE",
            resource_type="ACCESS_REVIEW",
            resource_id=review.id,
            after_state={"title": title, "scope": scope_val, "account_count": len(accounts_to_review)},
            change_reason=f"Initiated periodic access review: {title}",
        )

        return review

    async def complete_access_review(
        self,
        review_id: str,
        reviewer_id: str,
        decisions: List[Dict[str, Any]],
        findings: Optional[str] = None,
    ) -> Optional[AccessReview]:
        coll = self._get_reviews_coll()
        doc = await coll.find_one({"id": review_id})
        if not doc:
            return None

        now = datetime.now(timezone.utc)
        update = {
            "status": AccessReviewStatus.COMPLETED.value,
            "accounts_reviewed": decisions,
            "findings": findings,
            "completed_at": now,
            "completed_by": reviewer_id,
            "updated_at": now,
        }

        await coll.update_one({"id": review_id}, {"$set": update})
        updated = await coll.find_one({"id": review_id})

        await audit_service.log_action(
            actor_id=reviewer_id,
            actor_role="admin",
            action="APPROVE",
            resource_type="ACCESS_REVIEW",
            resource_id=review_id,
            after_state={"status": AccessReviewStatus.COMPLETED.value, "findings": findings},
            change_reason=f"Completed access review {review_id}",
        )

        return AccessReview.model_validate(updated)

    async def list_reviews(self) -> List[AccessReview]:
        coll = self._get_reviews_coll()
        cursor = coll.find({}).sort("period_end", DESCENDING)
        results = []
        async for doc in cursor:
            results.append(AccessReview.model_validate(doc))
        return results

    async def request_break_glass_access(
        self,
        user_id: str,
        user_email: str,
        requested_role: str,
        justification: str,
        target_scope: str,
        duration_hours: int = 2,
    ) -> BreakGlassSession:
        """
        Creates an audited, time-bounded Break-Glass emergency session.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=min(8, max(1, duration_hours)))

        session = BreakGlassSession(
            user_id=user_id,
            user_email=user_email,
            requested_role=requested_role,
            justification=justification,
            target_scope=target_scope,
            requested_at=now,
            expires_at=expires_at,
            status="ACTIVE",
        )

        coll = self._get_bg_coll()
        await coll.insert_one(session.model_dump())

        await audit_service.log_action(
            actor_id=user_id,
            actor_role="emergency_admin",
            action="CREATE",
            resource_type="BREAK_GLASS_SESSION",
            resource_id=session.id,
            after_state={"requested_role": requested_role, "justification": justification, "expires_at": expires_at.isoformat()},
            change_reason=f"Break-Glass Emergency Access Activated: {justification}",
        )

        return session

    async def revoke_break_glass_session(
        self,
        session_id: str,
        revoked_by: str,
    ) -> Optional[BreakGlassSession]:
        coll = self._get_bg_coll()
        doc = await coll.find_one({"id": session_id})
        if not doc:
            return None

        now = datetime.now(timezone.utc)
        await coll.update_one(
            {"id": session_id},
            {"$set": {"status": "REVOKED", "revoked_at": now, "revoked_by": revoked_by, "updated_at": now}},
        )

        updated = await coll.find_one({"id": session_id})

        await audit_service.log_action(
            actor_id=revoked_by,
            actor_role="admin",
            action="REVOKE",
            resource_type="BREAK_GLASS_SESSION",
            resource_id=session_id,
            after_state={"status": "REVOKED"},
            change_reason=f"Revoked break-glass session {session_id}",
        )

        return BreakGlassSession.model_validate(updated)

    async def list_break_glass_sessions(self) -> List[BreakGlassSession]:
        coll = self._get_bg_coll()
        cursor = coll.find({}).sort("requested_at", DESCENDING)
        results = []
        async for doc in cursor:
            results.append(BreakGlassSession.model_validate(doc))
        return results


access_governance_service = AccessGovernanceService()
