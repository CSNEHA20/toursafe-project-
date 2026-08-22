from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...models.identity import (
    ConsentType,
    CredentialStatus,
    KYCDocumentRecord,
    KYCStatus,
    ProviderStatus,
    TouristIdentityProfile,
)
from ...schemas.identity import (
    AuthorityTouristIdentityView,
    ConsentResponse,
    PrivacyCenterResponse,
    PublicVerificationResult,
    ResponderTouristIdentityView,
    TouristIdentityProfileUpdate,
    TouristSelfIdentityView,
)
from ..realtime_bus import RealtimeEventBus
from .consent_service import consent_service
from .kyc_service import kyc_service
from .provider_base import provider_registry

logger = logging.getLogger("toursafe.identity.service")


class IdentityService:
    """
    Dedicated Tourist Identity Management Service.
    Enforces privacy boundaries, data minimization DTO generation, and re-verification on sensitive profile updates.
    """

    def __init__(self, bus: Optional[RealtimeEventBus] = None):
        self.bus = bus or RealtimeEventBus()
        self.kyc = kyc_service
        self.consents = consent_service
        self.providers = provider_registry

    async def get_self_view(self, user_id: str) -> TouristSelfIdentityView:
        """Constructs tourist's sanitized self-view with minimal metadata."""
        db = get_database()
        profile = await self.kyc.get_or_create_identity_profile(user_id)

        # Count active documents and consents
        docs_count = await db["kyc_documents"].count_documents({"tourist_id": user_id})
        consents_count = await db["user_consents"].count_documents({"user_id": user_id, "granted": True})

        # Fetch active credential reference if present
        cred_doc = await db["digital_tourist_credentials"].find_one(
            {"user_id": user_id, "status": CredentialStatus.ACTIVE}
        )
        cred_ref = cred_doc.get("credential_reference") if cred_doc else None
        cred_status = cred_doc.get("status") if cred_doc else None

        return TouristSelfIdentityView(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            date_of_birth=profile.date_of_birth,
            nationality=profile.nationality,
            contact_phone=profile.contact_phone,
            contact_email=profile.contact_email,
            identity_status=profile.identity_status,
            verified_fields=profile.verified_fields,
            last_verified_at=profile.last_verified_at,
            verification_expires_at=profile.verification_expires_at,
            current_credential_reference=cred_ref,
            active_credential_status=cred_status,
            documents_count=docs_count,
            active_consents_count=consents_count,
        )

    async def update_profile(self, user_id: str, updates: TouristIdentityProfileUpdate) -> TouristIdentityProfile:
        """
        Updates tourist profile.
        CRITICAL: If sensitive verified fields (full_name, date_of_birth, nationality) are modified,
        triggers re-verification policy by transitioning status from VERIFIED to UNDER_REVIEW/REQUIRES_ACTION.
        """
        db = get_database()
        profile = await self.kyc.get_or_create_identity_profile(user_id)

        now = datetime.now(timezone.utc)
        requires_reverification = False

        if updates.full_name and updates.full_name != profile.full_name:
            if "full_name" in profile.verified_fields and profile.identity_status == KYCStatus.VERIFIED:
                requires_reverification = True
            profile.full_name = updates.full_name

        if updates.date_of_birth and updates.date_of_birth != profile.date_of_birth:
            if "date_of_birth" in profile.verified_fields and profile.identity_status == KYCStatus.VERIFIED:
                requires_reverification = True
            profile.date_of_birth = updates.date_of_birth

        if updates.nationality and updates.nationality != profile.nationality:
            if "nationality" in profile.verified_fields and profile.identity_status == KYCStatus.VERIFIED:
                requires_reverification = True
            profile.nationality = updates.nationality

        if updates.contact_phone:
            profile.contact_phone = updates.contact_phone
        if updates.contact_email:
            profile.contact_email = updates.contact_email

        if requires_reverification:
            logger.info("Material identity change detected for user %s. Triggering re-verification.", user_id)
            profile.identity_status = KYCStatus.UNDER_REVIEW
            profile.verified_fields = []
            # Suspend active credentials
            await db["digital_tourist_credentials"].update_many(
                {"user_id": user_id, "status": CredentialStatus.ACTIVE},
                {"$set": {"status": CredentialStatus.SUSPENDED, "suspension_reason": "Identity profile updated; re-verification required", "updated_at": now}},
            )

        profile.updated_at = now
        await db["tourist_identity_profiles"].update_one({"id": profile.id}, {"$set": profile.to_dict()})

        # Also keep User and Tourist collections in sync
        await db["users"].update_one(
            {"id": user_id},
            {"$set": {"full_name": profile.full_name, "phone": profile.contact_phone, "updated_at": now}},
        )
        await db["tourists"].update_one(
            {"user_id": user_id},
            {"$set": {"full_name": profile.full_name, "nationality": profile.nationality, "date_of_birth": profile.date_of_birth, "updated_at": now}},
        )

        await self.bus.publish_event(
            event_type="identity.updated",
            payload={
                "user_id": user_id,
                "identity_profile_id": profile.id,
                "requires_reverification": requires_reverification,
                "status": str(profile.identity_status),
            },
            target_user_id=user_id,
        )

        return profile

    async def get_authority_view(self, identity_profile_id: str) -> Optional[AuthorityTouristIdentityView]:
        """Authorized review view with masked document summaries and history count."""
        db = get_database()
        profile_doc = await db["tourist_identity_profiles"].find_one({"id": identity_profile_id})
        if not profile_doc:
            return None

        profile = TouristIdentityProfile.from_dict(profile_doc)

        docs_cursor = db["kyc_documents"].find({"identity_profile_id": profile.id})
        docs = await docs_cursor.to_list(length=20)
        doc_summaries = [
            {
                "id": d["id"],
                "document_type": d["document_type"],
                "masked_identifier": d["masked_identifier"],
                "verification_status": d["verification_status"],
                "submitted_at": d.get("submitted_at"),
            }
            for d in docs
        ]

        history_count = await db["kyc_verification_history"].count_documents({"identity_profile_id": profile.id})

        cred_doc = await db["digital_tourist_credentials"].find_one(
            {"user_id": profile.user_id, "status": CredentialStatus.ACTIVE}
        )

        return AuthorityTouristIdentityView(
            identity_profile_id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            date_of_birth=profile.date_of_birth,
            nationality=profile.nationality,
            identity_status=profile.identity_status,
            verified_fields=profile.verified_fields,
            last_verified_at=profile.last_verified_at,
            verification_expires_at=profile.verification_expires_at,
            current_credential_reference=cred_doc.get("credential_reference") if cred_doc else None,
            credential_status=cred_doc.get("status") if cred_doc else None,
            document_summaries=doc_summaries,
            verification_history_count=history_count,
        )

    async def get_responder_view(self, user_id: str) -> ResponderTouristIdentityView:
        """Minimal operational identity view for emergency responders without KYC docs."""
        db = get_database()
        profile = await self.kyc.get_or_create_identity_profile(user_id)

        cred_doc = await db["digital_tourist_credentials"].find_one(
            {"user_id": user_id, "status": CredentialStatus.ACTIVE}
        )

        return ResponderTouristIdentityView(
            user_id=user_id,
            full_name=profile.full_name,
            nationality=profile.nationality,
            contact_phone=profile.contact_phone,
            identity_verified=(profile.identity_status == KYCStatus.VERIFIED),
            identity_status=profile.identity_status,
            credential_reference=cred_doc.get("credential_reference") if cred_doc else None,
        )

    async def get_privacy_center(self, user_id: str) -> PrivacyCenterResponse:
        """Aggregated Privacy & Consent Center payload."""
        self_view = await self.get_self_view(user_id)
        user_consents = await self.consents.get_user_consents(user_id)

        consent_responses = [
            ConsentResponse(
                id=c.id,
                user_id=c.user_id,
                consent_type=c.consent_type,
                version=c.version,
                granted=c.granted,
                source=c.source,
                granted_at=c.granted_at,
                withdrawn_at=c.withdrawn_at,
                withdrawal_reason=c.withdrawal_reason,
            )
            for c in user_consents
        ]

        summary = {c_type.value: False for c_type in ConsentType}
        for c in user_consents:
            if c.granted:
                summary[c.consent_type] = True

        default_provider = self.providers.get_default_provider()
        provider_status = await default_provider.get_status()

        return PrivacyCenterResponse(
            identity_profile=self_view,
            active_consents=[c for c in consent_responses if c.granted],
            consents_summary=summary,
            real_provider_configured=default_provider.is_real_provider,
            provider_status=provider_status,
        )


# Global Identity Service Singleton
identity_service = IdentityService()
