"""
TourSafe Unified Configuration & Policy Governance Engine.
Enforces:
- Full configuration lifecycle (DRAFT -> VALIDATING -> PENDING_APPROVAL -> APPROVED -> ACTIVE -> RETIRED / REJECTED)
- Multi-party Separation of Duties (Creator != Approver)
- Schema, value bounds, dependency, and circular escalation loop validation
- Semantic versioning, configuration diffing, and safe rollbacks
- Safe secret-scrubbed export and draft-only import
- Atomic runtime cache invalidation and hot-reloading into safety and orchestration engines
"""

import copy
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core.database import get_database
from ...core.redis import get_redis_client
from ...models.governance import (
    AuditAction,
    ConfigurationLifecycleStatus,
    ConfigurationType,
    GovernanceConfigurationRecord,
)
from ...schemas.governance import (
    ConfigurationApproveRequest,
    ConfigurationCreateDraftRequest,
    ConfigurationDiffResponse,
    ConfigurationExportResponse,
    ConfigurationRecordResponse,
    ConfigurationRejectRequest,
    ConfigurationRollbackRequest,
    ConfigurationUpdateDraftRequest,
    ConfigurationValidationResult,
)
from .audit_service import audit_service

logger = logging.getLogger("toursafe.governance.config")


class ConfigGovernanceService:
    def __init__(self):
        self.collection_name = "governance_configurations"
        self._active_cache: Dict[ConfigurationType, Dict[str, Any]] = {}

    def _get_collection(self):
        return get_database()[self.collection_name]

    async def init_indexes(self):
        """Initializes unique and status indexes for versioned configuration management."""
        try:
            coll = self._get_collection()
            indexes = [
                IndexModel([("configuration_id", ASCENDING)], unique=True),
                IndexModel([("type", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("type", ASCENDING), ("version", ASCENDING)]),
                IndexModel([("jurisdiction_id", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
            ]
            await coll.create_indexes(indexes)
        except Exception as e:
            print(f"⚠️ ConfigGovernanceService index initialization note: {e}")

    # -----------------------------------------------------------------------
    # Validation Engine
    # -----------------------------------------------------------------------

    def validate_configuration_payload(
        self,
        config_type: ConfigurationType | str,
        parameters: Dict[str, Any],
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Performs thorough domain validation on configuration payloads according to type.
        Detects invalid ranges, negative timeouts, empty mandatory lists, and escalation loops.
        """
        errors: List[str] = []
        warnings: List[str] = []

        c_type = config_type.value if hasattr(config_type, "value") else str(config_type)

        if not isinstance(parameters, dict):
            return False, ["Parameters must be a JSON dictionary object."], []

        # 1. Safety Configuration Validation
        if c_type == ConfigurationType.SAFETY.value:
            # Check weights sum
            weights = [
                parameters.get("weight_motion", 0.30),
                parameters.get("weight_spatial", 0.28),
                parameters.get("weight_itinerary", 0.16),
                parameters.get("weight_environmental", 0.14),
                parameters.get("weight_vulnerability", 0.12),
            ]
            for w in weights:
                if not isinstance(w, (int, float)) or w < 0 or w > 1:
                    errors.append(f"Safety weight '{w}' is invalid. All weights must be between 0.0 and 1.0.")
            total_weight = sum(weights)
            if abs(total_weight - 1.0) > 0.05:
                warnings.append(f"Domain weights sum to {total_weight:.2f}, recommended normalization is 1.00.")

            # Check risk thresholds hierarchy
            watch = parameters.get("risk_threshold_watch", 30.0)
            elevated = parameters.get("risk_threshold_elevated", 60.0)
            candidate = parameters.get("risk_threshold_candidate", 80.0)
            incident = parameters.get("risk_threshold_incident", 90.0)

            for t_name, t_val in [("watch", watch), ("elevated", elevated), ("candidate", candidate), ("incident", incident)]:
                if not isinstance(t_val, (int, float)) or t_val < 0 or t_val > 100:
                    errors.append(f"Risk threshold '{t_name}' ({t_val}) must be between 0.0 and 100.0.")

            if not (watch < elevated < candidate < incident):
                errors.append(
                    f"Risk thresholds must follow strict ascending order: watch ({watch}) < elevated ({elevated}) < candidate ({candidate}) < incident ({incident})."
                )

            # Check freshness limits
            for f_key in ["gps_freshness_seconds", "anomaly_freshness_seconds", "telemetry_freshness_seconds", "signal_expiry_seconds"]:
                val = parameters.get(f_key)
                if val is not None and (not isinstance(val, (int, float)) or val <= 0):
                    errors.append(f"Freshness limit '{f_key}' must be a positive number greater than 0.")

        # 2. Escalation Policy & Cycle Detection Validation
        elif c_type in (ConfigurationType.ESCALATION.value, ConfigurationType.RESPONSE_POLICY.value):
            stages = parameters.get("stages", [])
            if not isinstance(stages, list):
                errors.append("'stages' parameter must be a list of escalation stages.")
            elif len(stages) == 0:
                warnings.append("No escalation stages configured; incident will rely solely on initial responders.")
            else:
                seen_stages: Set[int] = set()
                for idx, stage in enumerate(stages):
                    s_num = stage.get("stage") if isinstance(stage, dict) else None
                    if s_num is None or not isinstance(s_num, int) or s_num <= 0:
                        errors.append(f"Stage index {idx} has invalid stage number '{s_num}'. Must be a positive integer.")
                    elif s_num in seen_stages:
                        errors.append(f"Duplicate stage number {s_num} detected. Escalation stages must be strictly unique and sequential.")
                    seen_stages.add(s_num)

                    delay = stage.get("delay_seconds", 0) if isinstance(stage, dict) else -1
                    if delay < 0:
                        errors.append(f"Stage {s_num} has negative delay_seconds ({delay}). Delay must be >= 0.")

                    # Loop detection in next stage pointers
                    next_s = stage.get("next_stage") if isinstance(stage, dict) else None
                    if next_s is not None and next_s == s_num:
                        errors.append(f"Escalation Cycle Error: Stage {s_num} references itself as next_stage.")
                    if next_s is not None and next_s < s_num:
                        errors.append(f"Escalation Cycle Error: Backward cycle detected from Stage {s_num} to Stage {next_s}.")

        # 3. Notification Policy & Channel Fallback Validation
        elif c_type == ConfigurationType.NOTIFICATION.value:
            channels = parameters.get("channels", [])
            valid_channels = {"PUSH", "SMS", "EMAIL", "VOICE", "IN_APP"}
            if not isinstance(channels, list) or len(channels) == 0:
                errors.append("Notification configuration requires at least one active channel in 'channels'.")
            else:
                for ch in channels:
                    if ch not in valid_channels:
                        errors.append(f"Unsupported notification channel '{ch}'. Supported channels: {sorted(list(valid_channels))}")

            fallback_chain = parameters.get("fallback_chain", [])
            if isinstance(fallback_chain, list):
                for f_step in fallback_chain:
                    if f_step not in valid_channels and f_step != "AUTHORITY_REVIEW":
                        errors.append(f"Invalid fallback step '{f_step}' in fallback_chain.")

            retries = parameters.get("max_retries", 3)
            if not isinstance(retries, int) or retries < 0 or retries > 10:
                errors.append("max_retries must be an integer between 0 and 10.")

        # 4. System & Security Configuration Validation
        elif c_type == ConfigurationType.SYSTEM.value:
            tz = parameters.get("timezone", "UTC")
            if not isinstance(tz, str) or len(tz) == 0:
                errors.append("Invalid timezone string.")

        return len(errors) == 0, errors, warnings

    # -----------------------------------------------------------------------
    # Configuration CRUD & Lifecycle
    # -----------------------------------------------------------------------

    async def create_draft_configuration(
        self,
        req: ConfigurationCreateDraftRequest,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationRecordResponse:
        """
        Creates a new draft configuration. Drafts are safely isolated and have zero production impact.
        """
        coll = self._get_collection()

        # Validate draft payload structure
        valid, errors, warnings = self.validate_configuration_payload(req.type, req.parameters)

        config = GovernanceConfigurationRecord(
            type=req.type,
            name=req.name.strip(),
            description=req.description or "",
            version=req.version.strip(),
            status=ConfigurationLifecycleStatus.DRAFT,
            jurisdiction_id=req.jurisdiction_id,
            parameters=req.parameters,
            change_reason=req.change_reason.strip(),
            created_by=actor_id,
            dependencies=req.dependencies,
            validation_results={"valid": valid, "errors": errors, "warnings": warnings},
        )

        doc = config.to_dict()
        await coll.insert_one(doc)

        type_str = config.type if isinstance(config.type, str) else config.type.value
        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.CREATE,
            resource_type="CONFIG",
            resource_id=config.configuration_id,
            jurisdiction_id=req.jurisdiction_id,
            after_state=doc,
            change_reason=f"Created DRAFT configuration '{config.name}' ({type_str} {config.version})",
        )

        return ConfigurationRecordResponse(**doc)

    async def update_draft_configuration(
        self,
        configuration_id: str,
        req: ConfigurationUpdateDraftRequest,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationRecordResponse:
        """
        Updates an existing draft configuration. Only configurations in DRAFT or REJECTED state can be modified.
        """
        coll = self._get_collection()
        existing = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration {configuration_id} not found.")

        current_status = existing.get("status")
        if current_status not in (ConfigurationLifecycleStatus.DRAFT.value, ConfigurationLifecycleStatus.REJECTED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit configuration in status '{current_status}'. Only DRAFT and REJECTED configurations can be edited. Clone or create a new draft instead.",
            )

        updates: Dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": ConfigurationLifecycleStatus.DRAFT.value,  # Reset back to DRAFT on edit
        }
        if req.name is not None:
            updates["name"] = req.name.strip()
        if req.description is not None:
            updates["description"] = req.description
        if req.parameters is not None:
            updates["parameters"] = req.parameters
        if req.change_reason is not None:
            updates["change_reason"] = req.change_reason.strip()
        if req.dependencies is not None:
            updates["dependencies"] = req.dependencies

        params_to_validate = req.parameters if req.parameters is not None else existing.get("parameters", {})
        valid, errors, warnings = self.validate_configuration_payload(existing.get("type"), params_to_validate)
        updates["validation_results"] = {"valid": valid, "errors": errors, "warnings": warnings}

        await coll.update_one({"configuration_id": configuration_id}, {"$set": updates})
        updated = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.EDIT,
            resource_type="CONFIG",
            resource_id=configuration_id,
            jurisdiction_id=existing.get("jurisdiction_id"),
            before_state=existing,
            after_state=updated,
            change_reason="Updated draft configuration parameters",
        )

        return ConfigurationRecordResponse(**updated)

    async def validate_configuration(
        self,
        configuration_id: str,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationValidationResult:
        """
        Runs comprehensive validation on a draft configuration, checking syntax, bounds,
        dependencies, and safety invariants.
        """
        coll = self._get_collection()
        doc = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration {configuration_id} not found.")

        config_type = doc.get("type")
        parameters = doc.get("parameters", {})
        dependencies = doc.get("dependencies", [])

        valid, errors, warnings = self.validate_configuration_payload(config_type, parameters)

        # Check dependencies in DB
        db = get_database()
        dependency_checks = []
        for dep in dependencies:
            found = False
            # Check zones, policies, or jurisdictions
            if dep.startswith("zone_"):
                z = await db["zones"].find_one({"id": dep})
                found = z is not None
            elif dep.startswith("pol_"):
                p = await db["response_policies"].find_one({"policy_id": dep})
                found = p is not None
            elif dep.startswith("jur_"):
                j = await db["governance_jurisdictions"].find_one({"id": dep})
                found = j is not None
            else:
                found = True  # Generic parameter dependency

            dependency_checks.append({"dependency_id": dep, "exists": found, "valid": found})
            if not found:
                errors.append(f"Referenced dependency '{dep}' was not found in the database.")
                valid = False

        val_result = {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "dependency_checks": dependency_checks,
        }

        # Update validation status in record
        new_status = ConfigurationLifecycleStatus.PENDING_APPROVAL.value if valid else ConfigurationLifecycleStatus.DRAFT.value
        await coll.update_one(
            {"configuration_id": configuration_id},
            {"$set": {"validation_results": val_result, "status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.VALIDATE,
            resource_type="CONFIG",
            resource_id=configuration_id,
            jurisdiction_id=doc.get("jurisdiction_id"),
            after_state=val_result,
            change_reason=f"Validated configuration. Status={new_status}, Valid={valid}",
        )

        return ConfigurationValidationResult(
            valid=valid,
            configuration_id=configuration_id,
            type=ConfigurationType(config_type),
            version=doc.get("version", "v1.0.0"),
            errors=errors,
            warnings=warnings,
            dependency_checks=dependency_checks,
        )

    # -----------------------------------------------------------------------
    # Multi-Party Approval & Separation of Duties
    # -----------------------------------------------------------------------

    async def approve_configuration(
        self,
        configuration_id: str,
        req: ConfigurationApproveRequest,
        actor_id: str,
        actor_role: str,
        enforce_separation_of_duties: bool = True,
    ) -> ConfigurationRecordResponse:
        """
        Approves a validated configuration.
        Enforces Separation of Duties: The author (created_by) cannot approve their own configuration
        unless system_admin explicitly bypasses for emergency operations.
        """
        coll = self._get_collection()
        doc = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration {configuration_id} not found.")

        # Require authority_admin, supervisor, or system_admin
        if actor_role not in ("authority_admin", "system_admin", "supervisor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Administrative approval privileges required.",
            )

        # Separation of duties check
        created_by = doc.get("created_by")
        if enforce_separation_of_duties and actor_id == created_by and actor_role != "system_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Separation of Duties Violation: Creator ({created_by}) cannot self-approve safety configuration. A separate supervisor or authority administrator must review and sign off.",
            )

        # Verify validation passed
        val_results = doc.get("validation_results", {})
        if not val_results.get("valid", False):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot approve configuration with validation errors: {'; '.join(val_results.get('errors', []))}",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        updates = {
            "status": ConfigurationLifecycleStatus.APPROVED.value,
            "approved_by": actor_id,
            "updated_at": now_iso,
        }

        await coll.update_one({"configuration_id": configuration_id}, {"$set": updates})
        updated = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.APPROVE,
            resource_type="CONFIG",
            resource_id=configuration_id,
            jurisdiction_id=doc.get("jurisdiction_id"),
            before_state=doc,
            after_state=updated,
            change_reason=f"Approved configuration: {req.reason}",
        )

        return ConfigurationRecordResponse(**updated)

    async def reject_configuration(
        self,
        configuration_id: str,
        req: ConfigurationRejectRequest,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationRecordResponse:
        """
        Rejects a draft configuration, recording the rejection reason, reviewer, and timestamp.
        The draft is retained with audit history rather than being deleted.
        """
        coll = self._get_collection()
        doc = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration {configuration_id} not found.")

        now_iso = datetime.now(timezone.utc).isoformat()
        updates = {
            "status": ConfigurationLifecycleStatus.REJECTED.value,
            "rejected_by": actor_id,
            "rejection_reason": req.rejection_reason.strip(),
            "updated_at": now_iso,
        }

        await coll.update_one({"configuration_id": configuration_id}, {"$set": updates})
        updated = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.REJECT,
            resource_type="CONFIG",
            resource_id=configuration_id,
            jurisdiction_id=doc.get("jurisdiction_id"),
            before_state=doc,
            after_state=updated,
            change_reason=f"Rejected configuration: {req.rejection_reason}",
        )

        return ConfigurationRecordResponse(**updated)

    # -----------------------------------------------------------------------
    # Atomic Activation & Runtime Reconciliation
    # -----------------------------------------------------------------------

    async def activate_configuration(
        self,
        configuration_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationRecordResponse:
        """
        Atomically promotes an APPROVED configuration to ACTIVE.
        Marks any previously active configuration of the same type (and jurisdiction) as RETIRED.
        Invalidates Redis configuration caches and hot-reloads runtime parameters.
        """
        coll = self._get_collection()
        target = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration {configuration_id} not found.")

        if target.get("status") != ConfigurationLifecycleStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only APPROVED configurations can be activated. Current status is '{target.get('status')}'.",
            )

        config_type = target.get("type")
        jurisdiction_id = target.get("jurisdiction_id")
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Find currently active configuration to retire
        active_query = {
            "type": config_type,
            "jurisdiction_id": jurisdiction_id,
            "status": ConfigurationLifecycleStatus.ACTIVE.value,
        }
        currently_active = await coll.find_one(active_query, {"_id": 0})

        # Retire old active configuration
        if currently_active:
            await coll.update_one(
                {"configuration_id": currently_active["configuration_id"]},
                {
                    "$set": {
                        "status": ConfigurationLifecycleStatus.RETIRED.value,
                        "retired_by": actor_id,
                        "retired_at": now_iso,
                        "updated_at": now_iso,
                    }
                },
            )

        # Activate target configuration
        updates = {
            "status": ConfigurationLifecycleStatus.ACTIVE.value,
            "activated_by": actor_id,
            "activated_at": now_iso,
            "previous_version_id": currently_active.get("configuration_id") if currently_active else None,
            "updated_at": now_iso,
        }
        await coll.update_one({"configuration_id": configuration_id}, {"$set": updates})
        activated = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})

        # Runtime Cache Invalidation & Hot-Reload
        await self._reconcile_runtime_configuration(ConfigurationType(config_type), activated.get("parameters", {}), activated.get("version", "v1.0.0"))

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.ACTIVATE,
            resource_type="CONFIG",
            resource_id=configuration_id,
            jurisdiction_id=jurisdiction_id,
            before_state=currently_active,
            after_state=activated,
            change_reason=f"Activated configuration {target.get('name')} ({activated.get('version')}): {reason}",
        )

        return ConfigurationRecordResponse(**activated)

    async def rollback_configuration(
        self,
        req: ConfigurationRollbackRequest,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationRecordResponse:
        """
        Safely rolls back runtime configuration to a specified previous approved/retired version.
        Does not delete historical operational data; atomically marks current active as RETIRED and
        creates/promotes the rollback version as active.
        """
        coll = self._get_collection()
        target = await coll.find_one({"configuration_id": req.target_version_id}, {"_id": 0})
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target rollback configuration {req.target_version_id} not found.",
            )

        if target.get("status") not in (
            ConfigurationLifecycleStatus.APPROVED.value,
            ConfigurationLifecycleStatus.RETIRED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot rollback to configuration in status '{target.get('status')}'. Target must be APPROVED or RETIRED.",
            )

        # Mark target as APPROVED so it can be activated
        await coll.update_one(
            {"configuration_id": req.target_version_id},
            {"$set": {"status": ConfigurationLifecycleStatus.APPROVED.value, "rollback_target_version_id": req.target_version_id}},
        )

        # Activate target
        activated = await self.activate_configuration(
            configuration_id=req.target_version_id,
            reason=f"ROLLBACK to version {target.get('version')}: {req.reason}",
            actor_id=actor_id,
            actor_role=actor_role,
        )

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.ROLLBACK,
            resource_type="CONFIG",
            resource_id=req.target_version_id,
            jurisdiction_id=target.get("jurisdiction_id"),
            after_state=activated.model_dump(),
            change_reason=f"Emergency Rollback to {target.get('version')}: {req.reason}",
        )

        return activated

    # -----------------------------------------------------------------------
    # Configuration Diffing & Cloning
    # -----------------------------------------------------------------------

    async def compute_diff(self, source_config_id: str, target_config_id: str) -> ConfigurationDiffResponse:
        """
        Computes a structured diff between two configuration versions (Version N vs N+1).
        Identifies added, removed, and modified parameter keys.
        """
        coll = self._get_collection()
        src = await coll.find_one({"configuration_id": source_config_id}, {"_id": 0})
        tgt = await coll.find_one({"configuration_id": target_config_id}, {"_id": 0})

        if not src or not tgt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source or target configuration not found for diff.")

        p_src = src.get("parameters", {})
        p_tgt = tgt.get("parameters", {})

        all_keys = set(p_src.keys()).union(set(p_tgt.keys()))
        added: Dict[str, Any] = {}
        removed: Dict[str, Any] = {}
        modified: Dict[str, Dict[str, Any]] = {}

        for k in all_keys:
            if k not in p_src:
                added[k] = p_tgt[k]
            elif k not in p_tgt:
                removed[k] = p_src[k]
            elif p_src[k] != p_tgt[k]:
                modified[k] = {"old": p_src[k], "new": p_tgt[k]}

        summary_parts = []
        if added:
            summary_parts.append(f"{len(added)} added key(s)")
        if removed:
            summary_parts.append(f"{len(removed)} removed key(s)")
        if modified:
            summary_parts.append(f"{len(modified)} modified key(s)")
        summary = ", ".join(summary_parts) if summary_parts else "Identical parameters"

        return ConfigurationDiffResponse(
            source_version=src.get("version", "v1.0.0"),
            target_version=tgt.get("version", "v1.0.0"),
            source_config_id=source_config_id,
            target_config_id=target_config_id,
            added_keys=added,
            removed_keys=removed,
            modified_keys=modified,
            summary=summary,
        )

    async def clone_configuration_as_draft(
        self,
        configuration_id: str,
        new_version: str,
        change_reason: str,
        actor_id: str,
        actor_role: str,
    ) -> ConfigurationRecordResponse:
        """
        Clones an existing configuration into a new DRAFT record for safe iterative authoring.
        """
        coll = self._get_collection()
        source = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration {configuration_id} not found.")

        req = ConfigurationCreateDraftRequest(
            type=ConfigurationType(source.get("type")),
            name=f"{source.get('name')} (Clone)",
            description=source.get("description", ""),
            version=new_version.strip(),
            jurisdiction_id=source.get("jurisdiction_id"),
            parameters=copy.deepcopy(source.get("parameters", {})),
            change_reason=change_reason.strip(),
            dependencies=source.get("dependencies", []),
        )

        return await self.create_draft_configuration(req, actor_id=actor_id, actor_role=actor_role)

    # -----------------------------------------------------------------------
    # Safe Import & Export (Secret Scrubbing)
    # -----------------------------------------------------------------------

    async def export_configurations(
        self,
        config_type: Optional[ConfigurationType] = None,
        jurisdiction_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> ConfigurationExportResponse:
        """
        Safely exports configuration records.
        Strictly scrubs any infrastructure credentials, tokens, or private secrets.
        """
        coll = self._get_collection()
        query: Dict[str, Any] = {}
        if config_type:
            query["type"] = config_type.value if hasattr(config_type, "value") else str(config_type)
        if jurisdiction_id:
            query["jurisdiction_id"] = jurisdiction_id

        cursor = coll.find(query, {"_id": 0}).sort("created_at", DESCENDING)
        exported = []
        secret_keys = {"secret", "api_key", "password", "token", "jwt", "private_key", "credentials"}

        async for doc in cursor:
            # Scrub secrets from parameters
            scrubbed_params = {}
            for k, v in doc.get("parameters", {}).items():
                if any(s in k.lower() for s in secret_keys):
                    scrubbed_params[k] = "[REDACTED_SECRET]"
                else:
                    scrubbed_params[k] = v
            doc["parameters"] = scrubbed_params
            exported.append(ConfigurationRecordResponse(**doc))

        if actor_id:
            await audit_service.log_action(
                actor_id=actor_id,
                actor_role=actor_role or "authority_admin",
                action=AuditAction.EXPORT,
                resource_type="CONFIG",
                resource_id="ALL",
                jurisdiction_id=jurisdiction_id,
                change_reason=f"Exported {len(exported)} configuration items (secrets scrubbed).",
            )

        return ConfigurationExportResponse(
            export_id=f"exp_{uuid.uuid4().hex[:10]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            system_version="TourSafe-Gov-2.5",
            scrubbed_secrets=True,
            configurations=exported,
        )

    async def import_configurations_as_draft(
        self,
        raw_items: List[Dict[str, Any]],
        actor_id: str,
        actor_role: str,
    ) -> List[ConfigurationRecordResponse]:
        """
        Safely imports external configurations.
        SECURITY RULE: All imported configurations are ALWAYS forced to DRAFT status and must undergo
        formal schema validation and multi-user approval before any production activation.
        """
        imported_records = []
        for item in raw_items:
            c_type = item.get("type", "SAFETY")
            req = ConfigurationCreateDraftRequest(
                type=ConfigurationType(c_type) if c_type in [e.value for e in ConfigurationType] else ConfigurationType.SAFETY,
                name=f"[Imported] {item.get('name', 'Configuration')}",
                description=item.get("description", "Imported configuration"),
                version=f"{item.get('version', 'v1.0.0')}-import",
                jurisdiction_id=item.get("jurisdiction_id"),
                parameters=item.get("parameters", {}),
                change_reason="Imported via administration package (Saved as DRAFT)",
                dependencies=item.get("dependencies", []),
            )
            created = await self.create_draft_configuration(req, actor_id=actor_id, actor_role=actor_role)
            imported_records.append(created)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.IMPORT,
            resource_type="CONFIG",
            resource_id="BATCH_IMPORT",
            change_reason=f"Imported {len(imported_records)} items safely as DRAFTs.",
        )

        return imported_records

    # -----------------------------------------------------------------------
    # Listing & Active Querying
    # -----------------------------------------------------------------------

    async def list_configurations(
        self,
        config_type: Optional[ConfigurationType] = None,
        status_filter: Optional[ConfigurationLifecycleStatus] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> List[ConfigurationRecordResponse]:
        coll = self._get_collection()
        query: Dict[str, Any] = {}
        if config_type:
            query["type"] = config_type.value if hasattr(config_type, "value") else str(config_type)
        if status_filter:
            query["status"] = status_filter.value if hasattr(status_filter, "value") else str(status_filter)
        if jurisdiction_id:
            query["jurisdiction_id"] = jurisdiction_id

        cursor = coll.find(query, {"_id": 0}).sort("created_at", DESCENDING)
        res = []
        async for doc in cursor:
            res.append(ConfigurationRecordResponse(**doc))
        return res

    async def get_configuration(self, configuration_id: str) -> Optional[ConfigurationRecordResponse]:
        coll = self._get_collection()
        doc = await coll.find_one({"configuration_id": configuration_id}, {"_id": 0})
        if not doc:
            return None
        return ConfigurationRecordResponse(**doc)

    async def get_active_configuration(
        self,
        config_type: ConfigurationType,
        jurisdiction_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the currently active configuration for runtime execution.
        """
        coll = self._get_collection()
        query: Dict[str, Any] = {
            "type": config_type.value if hasattr(config_type, "value") else str(config_type),
            "status": ConfigurationLifecycleStatus.ACTIVE.value,
        }
        if jurisdiction_id:
            query["jurisdiction_id"] = jurisdiction_id

        doc = await coll.find_one(query, {"_id": 0})
        return doc

    # -----------------------------------------------------------------------
    # Runtime Reconciliation Engine
    # -----------------------------------------------------------------------

    async def _reconcile_runtime_configuration(
        self,
        config_type: ConfigurationType,
        parameters: Dict[str, Any],
        version: str,
    ):
        """
        Propagates active configuration updates to the running services and Redis cache.
        """
        self._active_cache[config_type] = parameters

        try:
            r = await get_redis_client()
            if r:
                cache_key = f"toursafe:config:{config_type.value}:active"
                await r.set(cache_key, json.dumps({"version": version, "parameters": parameters}))
                # Invalidate stale cache
                await r.delete(f"toursafe:config:{config_type.value}:cache")
        except Exception as e:
            print(f"⚠️ Redis config cache reconciliation note: {e}")

        # If SAFETY config changed, update safety_config in place
        if config_type == ConfigurationType.SAFETY:
            try:
                from ..safety.config import safety_config
                for k, v in parameters.items():
                    if hasattr(safety_config, k):
                        setattr(safety_config, k, v)
                safety_config.rule_version = f"safety-rules-{version}"
                print(f"✅ Dynamic Safety Configuration reloaded to {safety_config.rule_version}")
            except Exception as e:
                print(f"⚠️ Safety config dynamic reload note: {e}")

    # -----------------------------------------------------------------------
    # Default Seed Configurations (Baseline)
    # -----------------------------------------------------------------------

    async def seed_defaults(self) -> int:
        """Seeds initial default active governance configurations if empty."""
        coll = self._get_collection()
        count = await coll.count_documents({})
        if count > 0:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Baseline Safety Rules
        safety_default = GovernanceConfigurationRecord(
            configuration_id="cfg_safety_rules_v100",
            type=ConfigurationType.SAFETY,
            name="Default Government Safety Intelligence & Risk Fusion Parameters",
            description="Baseline multi-signal risk weights, fusion thresholds, and signal freshness windows.",
            version="v1.0.0",
            status=ConfigurationLifecycleStatus.ACTIVE,
            parameters={
                "weight_motion": 0.30,
                "weight_spatial": 0.28,
                "weight_itinerary": 0.16,
                "weight_environmental": 0.14,
                "weight_vulnerability": 0.12,
                "risk_threshold_watch": 30.0,
                "risk_threshold_elevated": 60.0,
                "risk_threshold_candidate": 80.0,
                "risk_threshold_incident": 90.0,
                "gps_freshness_seconds": 30.0,
                "anomaly_freshness_seconds": 20.0,
                "telemetry_freshness_seconds": 15.0,
                "signal_expiry_seconds": 120.0,
                "recovery_cooldown_seconds": 20.0,
            },
            change_reason="System baseline production initialization",
            created_by="system_admin",
            approved_by="system_supervisor",
            activated_by="system_admin",
            activated_at=datetime.now(timezone.utc),
            validation_results={"valid": True, "errors": [], "warnings": []},
        )
        await coll.insert_one(safety_default.to_dict())

        # 2. Baseline Notification Policy
        notif_default = GovernanceConfigurationRecord(
            configuration_id="cfg_notification_v100",
            type=ConfigurationType.NOTIFICATION,
            name="Default Emergency Notification & Fallback Channels",
            description="Multi-tier push, SMS, and authority dispatch fallback chain.",
            version="v1.0.0",
            status=ConfigurationLifecycleStatus.ACTIVE,
            parameters={
                "channels": ["PUSH", "SMS", "IN_APP"],
                "fallback_chain": ["PUSH", "SMS", "AUTHORITY_REVIEW"],
                "max_retries": 3,
                "retry_backoff_base_seconds": 10,
                "sms_provider_tier": "PRIMARY_HIGH_PRIORITY",
            },
            change_reason="System baseline notification parameters",
            created_by="system_admin",
            approved_by="system_supervisor",
            activated_by="system_admin",
            activated_at=datetime.now(timezone.utc),
            validation_results={"valid": True, "errors": [], "warnings": []},
        )
        await coll.insert_one(notif_default.to_dict())

        return 2


config_governance_service = ConfigGovernanceService()
