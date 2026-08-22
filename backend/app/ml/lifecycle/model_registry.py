"""
TourSafe Model Registry & Governance Service.
Manages the authoritative model catalog, immutable version metadata,
state machine transitions, explicit human approvals, production model pointer,
and auditable deployment/rollback logs in MongoDB collection 'ml_models'.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pymongo.errors import DuplicateKeyError

from ...core import database as db_core
from ...schemas.ml_lifecycle import (
    DeploymentAuditRecord,
    ModelApprovalRecord,
    ModelLifecycleStatus,
    ModelRegistryEntry,
    ModelValidationGateResult,
)
from .model_validator import model_validation_gate

logger = logging.getLogger("toursafe.ml.model_registry")

# Valid state machine transitions
ALLOWED_TRANSITIONS: Dict[ModelLifecycleStatus, List[ModelLifecycleStatus]] = {
    ModelLifecycleStatus.TRAINED: [
        ModelLifecycleStatus.VALIDATED,
        ModelLifecycleStatus.REJECTED,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.VALIDATED: [
        ModelLifecycleStatus.APPROVED,
        ModelLifecycleStatus.REJECTED,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.APPROVED: [
        ModelLifecycleStatus.STAGING,
        ModelLifecycleStatus.SHADOW,
        ModelLifecycleStatus.CANARY,
        ModelLifecycleStatus.PRODUCTION,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.STAGING: [
        ModelLifecycleStatus.SHADOW,
        ModelLifecycleStatus.CANARY,
        ModelLifecycleStatus.PRODUCTION,
        ModelLifecycleStatus.APPROVED,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.SHADOW: [
        ModelLifecycleStatus.CANARY,
        ModelLifecycleStatus.PRODUCTION,
        ModelLifecycleStatus.APPROVED,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.CANARY: [
        ModelLifecycleStatus.PRODUCTION,
        ModelLifecycleStatus.APPROVED,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.PRODUCTION: [
        ModelLifecycleStatus.ROLLED_BACK,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.ROLLED_BACK: [
        ModelLifecycleStatus.APPROVED,
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.REJECTED: [
        ModelLifecycleStatus.ARCHIVED,
    ],
    ModelLifecycleStatus.ARCHIVED: [],
}


class ModelRegistryService:
    """
    State machine and persistence layer for model governance.
    """

    async def init_indexes(self):
        try:
            db = db_core.get_database()
            await db.ml_models.create_index("model_version", unique=True)
            await db.ml_models.create_index("status")
            await db.ml_models.create_index("is_production")
            await db.ml_models.create_index("is_shadow")
            await db.ml_models.create_index("created_at")
        except Exception as e:
            logger.warning(f"Could not initialize ml_models indexes: {e}")

    async def register_model(self, entry: ModelRegistryEntry) -> bool:
        """Registers a newly trained model into the registry."""
        db = db_core.get_database()
        doc = entry.model_dump()
        try:
            await db.ml_models.insert_one(doc)
            logger.info(f"Registered new model version: {entry.model_version}")
            return True
        except DuplicateKeyError:
            logger.warning(f"Model version {entry.model_version} is already registered and immutable")
            return False
        except Exception as e:
            logger.error(f"Failed to persist model registry entry: {e}")
            return False

    async def get_model(self, model_version: str) -> Optional[ModelRegistryEntry]:
        db = db_core.get_database()
        doc = await db.ml_models.find_one({"model_version": model_version})
        if not doc:
            return None
        doc.pop("_id", None)
        return ModelRegistryEntry.model_validate(doc)

    async def get_production_model(self) -> Optional[ModelRegistryEntry]:
        """Resolves the currently active authoritative production model."""
        db = db_core.get_database()
        doc = await db.ml_models.find_one({"is_production": True, "status": ModelLifecycleStatus.PRODUCTION.value})
        if not doc:
            # Fallback to any model marked PRODUCTION or v1.0.0
            doc = await db.ml_models.find_one({"status": ModelLifecycleStatus.PRODUCTION.value})
        if not doc:
            return None
        doc.pop("_id", None)
        return ModelRegistryEntry.model_validate(doc)

    async def get_shadow_model(self) -> Optional[ModelRegistryEntry]:
        """Resolves active shadow candidate model if one is deployed."""
        db = db_core.get_database()
        doc = await db.ml_models.find_one({"is_shadow": True})
        if not doc:
            return None
        doc.pop("_id", None)
        return ModelRegistryEntry.model_validate(doc)

    async def list_models(
        self,
        status: Optional[ModelLifecycleStatus] = None,
        limit: int = 50,
    ) -> List[ModelRegistryEntry]:
        db = db_core.get_database()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value

        cursor = db.ml_models.find(query).sort("created_at", -1).limit(limit)
        models = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                models.append(ModelRegistryEntry.model_validate(doc))
            except Exception as e:
                logger.error(f"Error parsing model doc: {e}")
        return models

    async def validate_model(self, model_version: str) -> ModelValidationGateResult:
        """Executes pre-approval validation gate."""
        entry = await self.get_model(model_version)
        if not entry:
            raise ValueError(f"Model version '{model_version}' not found")

        gate_res = model_validation_gate.validate_model_version(model_version)

        db = db_core.get_database()
        new_status = ModelLifecycleStatus.VALIDATED if gate_res.passed_all_gates else ModelLifecycleStatus.REJECTED

        await db.ml_models.update_one(
            {"model_version": model_version},
            {
                "$set": {
                    "validation_gate": gate_res.model_dump(),
                    "status": new_status.value,
                }
            },
        )
        return gate_res

    async def approve_model(
        self,
        model_version: str,
        approver: str,
        reason: str,
        evaluation_summary: Optional[Dict[str, Any]] = None,
    ) -> ModelRegistryEntry:
        """Explicit human approval action."""
        entry = await self.get_model(model_version)
        if not entry:
            raise ValueError(f"Model version '{model_version}' not found")

        if entry.status not in [ModelLifecycleStatus.VALIDATED, ModelLifecycleStatus.TRAINED]:
            if entry.status == ModelLifecycleStatus.APPROVED:
                return entry
            raise ValueError(f"Cannot approve model in status '{entry.status}'. Must be VALIDATED or TRAINED.")

        # Ensure validation gate passed
        if not entry.validation_gate or not entry.validation_gate.passed_all_gates:
            gate_res = model_validation_gate.validate_model_version(model_version)
            if not gate_res.passed_all_gates:
                raise ValueError(f"Model validation gate failed! Errors: {gate_res.errors}")
            entry.validation_gate = gate_res

        approval = ModelApprovalRecord(
            approved_by=approver,
            approved_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            evaluation_summary=evaluation_summary or {},
        )

        db = db_core.get_database()
        await db.ml_models.update_one(
            {"model_version": model_version},
            {
                "$set": {
                    "status": ModelLifecycleStatus.APPROVED.value,
                    "approval": approval.model_dump(),
                    "validation_gate": entry.validation_gate.model_dump() if entry.validation_gate else None,
                }
            },
        )

        updated = await self.get_model(model_version)
        logger.info(f"Model {model_version} approved by {approver}")
        return updated or entry

    async def deploy_to_environment(
        self,
        model_version: str,
        target_status: ModelLifecycleStatus,
        deployed_by: str,
        reason: str,
        canary_percentage: float = 0.0,
    ) -> ModelRegistryEntry:
        """
        Transitions model to STAGING, SHADOW, CANARY, or PRODUCTION.
        """
        entry = await self.get_model(model_version)
        if not entry:
            raise ValueError(f"Model version '{model_version}' not found")

        # Governance Check: Must be APPROVED before deployment to any operational tier
        if entry.status not in [ModelLifecycleStatus.APPROVED, ModelLifecycleStatus.STAGING, ModelLifecycleStatus.SHADOW, ModelLifecycleStatus.CANARY]:
            if target_status == ModelLifecycleStatus.PRODUCTION and entry.status != ModelLifecycleStatus.PRODUCTION:
                raise ValueError(f"Governance violation: Model '{model_version}' status is '{entry.status}'. Must be APPROVED before deployment.")

        current_prod = await self.get_production_model()
        prev_version = current_prod.model_version if current_prod else None

        audit = DeploymentAuditRecord(
            model_version=model_version,
            previous_model_version=prev_version,
            action=f"DEPLOY_{target_status.value}",
            deployed_by=deployed_by,
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment="production" if target_status == ModelLifecycleStatus.PRODUCTION else "staging",
            reason=reason,
            details={"canary_percentage": canary_percentage},
        )

        db = db_core.get_database()

        if target_status == ModelLifecycleStatus.PRODUCTION:
            # Atomic displacement of current production model
            if current_prod and current_prod.model_version != model_version:
                await db.ml_models.update_one(
                    {"model_version": current_prod.model_version},
                    {
                        "$set": {
                            "is_production": False,
                            "status": ModelLifecycleStatus.APPROVED.value,
                        }
                    },
                )

            await db.ml_models.update_one(
                {"model_version": model_version},
                {
                    "$set": {
                        "is_production": True,
                        "is_shadow": False,
                        "is_staging": False,
                        "is_canary": False,
                        "status": ModelLifecycleStatus.PRODUCTION.value,
                    },
                    "$push": {"deployment_history": audit.model_dump()},
                },
            )
        elif target_status == ModelLifecycleStatus.SHADOW:
            # Reset existing shadow flags
            await db.ml_models.update_many({}, {"$set": {"is_shadow": False}})
            await db.ml_models.update_one(
                {"model_version": model_version},
                {
                    "$set": {
                        "is_shadow": True,
                        "status": ModelLifecycleStatus.SHADOW.value,
                    },
                    "$push": {"deployment_history": audit.model_dump()},
                },
            )
        elif target_status == ModelLifecycleStatus.CANARY:
            await db.ml_models.update_one(
                {"model_version": model_version},
                {
                    "$set": {
                        "is_canary": True,
                        "canary_percentage": canary_percentage,
                        "status": ModelLifecycleStatus.CANARY.value,
                    },
                    "$push": {"deployment_history": audit.model_dump()},
                },
            )
        elif target_status == ModelLifecycleStatus.STAGING:
            await db.ml_models.update_one(
                {"model_version": model_version},
                {
                    "$set": {
                        "is_staging": True,
                        "status": ModelLifecycleStatus.STAGING.value,
                    },
                    "$push": {"deployment_history": audit.model_dump()},
                },
            )

        updated = await self.get_model(model_version)
        logger.info(f"Model {model_version} transitioned to {target_status.value} by {deployed_by}")
        return updated or entry

    async def rollback(
        self,
        target_model_version: str,
        actor: str,
        reason: str,
    ) -> ModelRegistryEntry:
        """
        Restores a specified previous model version to PRODUCTION and marks displaced model ROLLED_BACK.
        """
        target = await self.get_model(target_model_version)
        if not target:
            raise ValueError(f"Rollback target model version '{target_model_version}' not found")

        current_prod = await self.get_production_model()
        displaced_version = current_prod.model_version if current_prod else None

        if displaced_version == target_model_version:
            raise ValueError(f"Model '{target_model_version}' is already the active production model")

        audit = DeploymentAuditRecord(
            model_version=target_model_version,
            previous_model_version=displaced_version,
            action="ROLLBACK",
            deployed_by=actor,
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment="production",
            reason=reason,
            details={"displaced_version": displaced_version},
        )

        db = db_core.get_database()

        # Mark displaced model as ROLLED_BACK
        if displaced_version:
            await db.ml_models.update_one(
                {"model_version": displaced_version},
                {
                    "$set": {
                        "is_production": False,
                        "status": ModelLifecycleStatus.ROLLED_BACK.value,
                    },
                    "$push": {"rollback_history": audit.model_dump()},
                },
            )

        # Reactivate target model as PRODUCTION
        await db.ml_models.update_one(
            {"model_version": target_model_version},
            {
                "$set": {
                    "is_production": True,
                    "is_shadow": False,
                    "is_staging": False,
                    "status": ModelLifecycleStatus.PRODUCTION.value,
                },
                "$push": {"deployment_history": audit.model_dump()},
            },
        )

        updated = await self.get_model(target_model_version)
        logger.warning(f"🚨 PRODUCTION ROLLBACK EXECUTED: Restored {target_model_version}, displaced {displaced_version} by {actor}")
        return updated or target


model_registry = ModelRegistryService()
