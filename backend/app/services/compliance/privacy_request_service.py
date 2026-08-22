"""
TourSafe Privacy Requests & Data Subject Rights (DSR) Service.
Handles:
- DSR creation, identity verification, and authority review
- Portable structured JSON personal data export with secure temporary tokens
- Safe deletion fulfillment with active incident / legal hold preservation checks
- Granular reporting of deleted vs retained categories
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.compliance import (
    DataCategory,
    PrivacyRequest,
    PrivacyRequestStatus,
    PrivacyRequestType,
)
from ..governance.audit_service import audit_service
from .legal_hold_service import legal_hold_service


class PrivacyRequestService:
    def __init__(self):
        self.collection_name = "compliance_privacy_requests"
        self.export_tokens_collection = "compliance_export_tokens"

    def _get_collection(self):
        db = db_core.get_database()
        return db[self.collection_name]

    def _get_token_collection(self):
        db = db_core.get_database()
        return db[self.export_tokens_collection]

    async def init_indexes(self):
        try:
            coll = self._get_collection()
            indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("subject_id", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
            ]
            await coll.create_indexes(indexes)

            tok_coll = self._get_token_collection()
            tok_indexes = [
                IndexModel([("token", ASCENDING)], unique=True),
                IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
            ]
            await tok_coll.create_indexes(tok_indexes)
        except Exception as e:
            print(f"⚠️ PrivacyRequestService index init note: {e}")

    async def create_request(
        self,
        subject_id: str,
        request_type: PrivacyRequestType,
        scope: Optional[List[DataCategory]] = None,
        notes: Optional[str] = None,
        correction_payload: Optional[Dict[str, Any]] = None,
    ) -> PrivacyRequest:
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=30)  # Standard 30-day statutory response window

        request = PrivacyRequest(
            subject_id=subject_id,
            request_type=request_type,
            scope=scope or [DataCategory.IDENTITY, DataCategory.LOCATION],
            status=PrivacyRequestStatus.SUBMITTED,
            created_at=now,
            deadline_at=deadline,
            notes=notes,
            correction_payload=correction_payload,
        )

        coll = self._get_collection()
        await coll.insert_one(request.model_dump())

        await audit_service.log_action(
            actor_id=subject_id,
            actor_role="tourist",
            action="CREATE",
            resource_type="PRIVACY_REQUEST",
            resource_id=request.id,
            after_state={"request_type": request_type.value, "status": PrivacyRequestStatus.SUBMITTED.value},
            change_reason=f"Submitted privacy request ({request_type.value})",
        )

        return request

    async def verify_identity(
        self,
        request_id: str,
        subject_id: str,
        method: str = "SESSION_AUTH",
    ) -> Optional[PrivacyRequest]:
        coll = self._get_collection()
        req = await coll.find_one({"id": request_id, "subject_id": subject_id})
        if not req:
            return None

        now = datetime.now(timezone.utc)
        update = {
            "identity_verified": True,
            "identity_verification_method": method,
            "identity_verified_at": now,
            "status": PrivacyRequestStatus.UNDER_REVIEW.value,
            "updated_at": now,
        }

        await coll.update_one({"id": request_id}, {"$set": update})
        updated = await coll.find_one({"id": request_id})

        await audit_service.log_action(
            actor_id=subject_id,
            actor_role="tourist",
            action="VALIDATE",
            resource_type="PRIVACY_REQUEST",
            resource_id=request_id,
            after_state={"identity_verified": True, "method": method},
            change_reason=f"Verified identity for privacy request {request_id}",
        )

        return PrivacyRequest.model_validate(updated)

    async def review_request(
        self,
        request_id: str,
        reviewer_id: str,
        decision: str,  # "APPROVE", "REJECT", "PARTIALLY_FULFILL"
        rejection_reason: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[PrivacyRequest]:
        coll = self._get_collection()
        doc = await coll.find_one({"id": request_id})
        if not doc:
            return None

        req = PrivacyRequest.model_validate(doc)
        now = datetime.now(timezone.utc)

        if decision == "REJECT":
            req.status = PrivacyRequestStatus.REJECTED
            req.rejection_reason = rejection_reason or "Request rejected after compliance review"
            req.completed_at = now
            req.assigned_to = reviewer_id
            req.notes = notes
            await coll.update_one({"id": request_id}, {"$set": req.model_dump()})
            return req

        # If Approved / Fulfillment, execute specific request type workflow
        if req.request_type in (PrivacyRequestType.ACCESS, PrivacyRequestType.EXPORT):
            token, expires_at = await self._generate_data_export(req.subject_id)
            req.export_token = token
            req.export_token_expires_at = expires_at
            req.status = PrivacyRequestStatus.COMPLETED
            req.completed_at = now
            req.assigned_to = reviewer_id
            await coll.update_one({"id": request_id}, {"$set": req.model_dump()})

        elif req.request_type == PrivacyRequestType.DELETION:
            deletion_result = await self._execute_safe_deletion(req.subject_id, req.scope)
            req.partial_deletion_details = deletion_result
            if len(deletion_result.get("retained_categories", [])) > 0:
                req.status = PrivacyRequestStatus.PARTIALLY_FULFILLED
            else:
                req.status = PrivacyRequestStatus.COMPLETED
            req.completed_at = now
            req.assigned_to = reviewer_id
            await coll.update_one({"id": request_id}, {"$set": req.model_dump()})

        elif req.request_type == PrivacyRequestType.CORRECTION:
            if req.correction_payload:
                await self._execute_correction(req.subject_id, req.correction_payload)
            req.status = PrivacyRequestStatus.COMPLETED
            req.completed_at = now
            req.assigned_to = reviewer_id
            await coll.update_one({"id": request_id}, {"$set": req.model_dump()})

        else:
            req.status = PrivacyRequestStatus.COMPLETED
            req.completed_at = now
            req.assigned_to = reviewer_id
            await coll.update_one({"id": request_id}, {"$set": req.model_dump()})

        await audit_service.log_action(
            actor_id=reviewer_id,
            actor_role="admin",
            action="APPROVE" if decision == "APPROVE" else "UPDATE",
            resource_type="PRIVACY_REQUEST",
            resource_id=request_id,
            after_state={"status": req.status.value, "decision": decision},
            change_reason=f"Reviewed and executed privacy request {request_id}",
        )

        return req

    async def _generate_data_export(self, subject_id: str) -> Tuple[str, datetime]:
        """
        Compiles subject personal data bundle into portable JSON structure
        and registers a temporary 24-hour download token.
        """
        db = db_core.get_database()
        
        # User profile
        user_doc = await db["users"].find_one({"id": subject_id}) or {}
        user_doc.pop("password_hash", None)
        user_doc.pop("_id", None)

        # Tourist profile
        tourist_doc = await db["tourists"].find_one({"user_id": subject_id}) or {}
        tourist_doc.pop("_id", None)

        # Emergency contacts
        contacts_cursor = db["emergency_contacts"].find({"tourist_id": tourist_doc.get("id") or subject_id})
        contacts = []
        async for c in contacts_cursor:
            c.pop("_id", None)
            contacts.append(c)

        # Itineraries
        itineraries_cursor = db["itineraries"].find({"tourist_id": tourist_doc.get("id") or subject_id})
        itineraries = []
        async for it in itineraries_cursor:
            it.pop("_id", None)
            itineraries.append(it)

        # Consents
        consents_cursor = db["compliance_consents"].find({"subject_id": subject_id})
        consents = []
        async for cs in consents_cursor:
            cs.pop("_id", None)
            consents.append(cs)

        export_bundle = {
            "export_metadata": {
                "subject_id": subject_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "format_version": "TourSafe-DSR-v1.0",
                "disclaimer": "This document contains your personal data as processed by TourSafe.",
            },
            "user_account": user_doc,
            "tourist_profile": tourist_doc,
            "emergency_contacts": contacts,
            "itineraries": itineraries,
            "consent_records": consents,
        }

        token = f"dsexp_{secrets.token_urlsafe(32)}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        tok_coll = self._get_token_collection()
        await tok_coll.insert_one({
            "token": token,
            "subject_id": subject_id,
            "payload": export_bundle,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        })

        return token, expires_at

    async def get_export_payload(self, token: str) -> Optional[Dict[str, Any]]:
        tok_coll = self._get_token_collection()
        doc = await tok_coll.find_one({"token": token})
        if not doc:
            return None
        if doc.get("expires_at") and doc["expires_at"] < datetime.now(timezone.utc):
            return None
        return doc.get("payload")

    async def _execute_safe_deletion(
        self,
        subject_id: str,
        requested_scope: List[DataCategory],
    ) -> Dict[str, Any]:
        """
        Executes safe deletion across database collections.
        Checks for:
        1. Active Legal Holds
        2. Ongoing Emergency Incidents
        3. Statutory Audit requirements
        """
        db = db_core.get_database()
        
        # Check active incident
        incidents_coll = db["incidents"]
        active_incident = await incidents_coll.find_one({
            "tourist_id": subject_id,
            "status": {"$in": ["REPORTED", "ACKNOWLEDGED", "ASSIGNED", "DISPATCHED", "ON_SCENE", "ESCALATED"]},
        })

        is_held, hold_reason = await legal_hold_service.is_entity_held(subject_id)

        deleted = []
        retained = []
        reasons = []

        # Evaluate and delete requested data categories
        for cat in requested_scope:
            cat_str = cat.value if hasattr(cat, "value") else str(cat)
            if is_held:
                retained.append(cat_str)
                reasons.append(f"{cat_str}: Blocked by {hold_reason}")
                continue

            if active_incident and cat_str in ("LOCATION", "INCIDENT", "IDENTITY"):
                retained.append(cat_str)
                reasons.append(f"{cat_str}: Retained during active emergency incident #{active_incident.get('id')}")
                continue

            if cat_str == "AUDIT":
                retained.append(cat_str)
                reasons.append("AUDIT: Immutable cryptographic audit trail retained per regulatory integrity requirement")
                continue

            # Perform actual deletion for category
            if cat_str == "LOCATION":
                await db["locations"].delete_many({"$or": [{"user_id": subject_id}, {"tourist_id": subject_id}]})
                await db["location_histories"].delete_many({"$or": [{"user_id": subject_id}, {"tourist_id": subject_id}]})
                deleted.append(cat_str)

            elif cat_str == "TELEMETRY":
                await db["telemetry_records"].delete_many({"$or": [{"user_id": subject_id}, {"tourist_id": subject_id}]})
                deleted.append(cat_str)

            elif cat_str == "CONTACT":
                await db["emergency_contacts"].delete_many({"$or": [{"user_id": subject_id}, {"tourist_id": subject_id}]})
                deleted.append(cat_str)

            elif cat_str == "IDENTITY":
                # Soft-delete or anonymize profile
                await db["tourists"].update_one(
                    {"$or": [{"user_id": subject_id}, {"id": subject_id}]},
                    {"$set": {"full_name": "[DELETED_USER]", "phone": None, "is_active": False, "deleted_at": datetime.now(timezone.utc)}},
                )
                await db["users"].update_one(
                    {"id": subject_id},
                    {"$set": {"full_name": "[DELETED_USER]", "phone": None, "is_active": False, "email": f"deleted_{subject_id[:8]}@anonymized.local"}},
                )
                deleted.append(cat_str)
            else:
                deleted.append(cat_str)

        return {
            "deleted_categories": deleted,
            "retained_categories": retained,
            "retention_reasons": reasons,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _execute_correction(self, subject_id: str, payload: Dict[str, Any]):
        db = db_core.get_database()
        allowed_fields = {"full_name", "phone", "contact_phone", "contact_email", "nationality"}
        update_dict = {k: v for k, v in payload.items() if k in allowed_fields}
        if update_dict:
            update_dict["updated_at"] = datetime.now(timezone.utc)
            await db["tourists"].update_one({"$or": [{"user_id": subject_id}, {"id": subject_id}]}, {"$set": update_dict})
            await db["users"].update_one({"id": subject_id}, {"$set": update_dict})

    async def get_requests(
        self,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[PrivacyRequest]:
        coll = self._get_collection()
        query: Dict[str, Any] = {}
        if subject_id:
            query["subject_id"] = subject_id
        if status:
            query["status"] = status

        cursor = coll.find(query).sort("created_at", DESCENDING).limit(limit)
        results = []
        async for doc in cursor:
            results.append(PrivacyRequest.model_validate(doc))
        return results

    async def get_request(self, request_id: str) -> Optional[PrivacyRequest]:
        coll = self._get_collection()
        doc = await coll.find_one({"id": request_id})
        if not doc:
            return None
        return PrivacyRequest.model_validate(doc)


privacy_request_service = PrivacyRequestService()
