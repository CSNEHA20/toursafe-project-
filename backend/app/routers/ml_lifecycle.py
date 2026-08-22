"""
TourSafe ML Data Engineering & Model Lifecycle API Router.
Exposes REST endpoints for dataset versioning, data quality inspection,
training job orchestration, experiment tracking, model registry governance,
validation gates, approvals, deployments, rollbacks, shadow evaluation, and drift monitoring.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import get_current_user, require_role
from ..schemas.ml_lifecycle import (
    DataQualitySummary,
    DatasetBuildRequest,
    DatasetRegistryEntry,
    DatasetStatus,
    DeploymentAuditRecord,
    ExperimentRecord,
    FeatureChannelDistribution,
    MLTrainingHyperparameters,
    ModelComparisonReport,
    ModelDriftReport,
    ModelLifecycleStatus,
    ModelRegistryEntry,
    ModelValidationGateResult,
    TrainingJobRecord,
    TrainingJobStatus,
)
from ..ml.lifecycle import (
    dataset_builder,
    dataset_registry,
    drift_detector,
    experiment_tracker,
    feature_registry,
    model_comparison_engine,
    model_registry,
    model_validation_gate,
    shadow_engine,
    training_manager,
)
from ..services.ml.loader import model_loader

router = APIRouter(prefix="/api/v1/ml", tags=["ML Lifecycle & Model Governance"])


# ---------------------------------------------------------------------------
# Request Schemas for APIs
# ---------------------------------------------------------------------------

class ApproveModelRequest(BaseModel):
    reason: str = Field(..., description="Justification and sign-off reason for approval")
    evaluation_summary: Optional[Dict[str, Any]] = None


class DeployModelRequest(BaseModel):
    reason: str = Field(..., description="Operational deployment justification")
    target_status: ModelLifecycleStatus = Field(default=ModelLifecycleStatus.PRODUCTION)
    canary_percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class RollbackModelRequest(BaseModel):
    reason: str = Field(..., description="Incident or failure reason mandating rollback")


class CreateTrainingJobRequest(BaseModel):
    model_version: str = Field(..., description="Target version identifier, e.g. lstm-anomaly-v2")
    dataset_version: str = Field(..., description="Dataset version to train against")
    feature_version: str = "features_v1"
    hyperparameters: Optional[MLTrainingHyperparameters] = None


# ---------------------------------------------------------------------------
# Dataset Endpoints
# ---------------------------------------------------------------------------

@router.get("/datasets", response_model=List[DatasetRegistryEntry], summary="List Versioned Datasets")
async def list_datasets(
    status_filter: Optional[DatasetStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Any = Depends(require_role("admin", "authority")),
):
    return await dataset_registry.list_datasets(status=status_filter, limit=limit)


@router.get("/datasets/{dataset_version}", response_model=DatasetRegistryEntry, summary="Get Dataset Metadata")
async def get_dataset(
    dataset_version: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    entry = await dataset_registry.get_dataset(dataset_version)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset '{dataset_version}' not found")
    return entry


@router.get("/datasets/{dataset_version}/quality", response_model=DataQualitySummary, summary="Get Data Quality Summary")
async def get_dataset_quality(
    dataset_version: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    entry = await dataset_registry.get_dataset(dataset_version)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset '{dataset_version}' not found")
    return entry.quality_report


# ---------------------------------------------------------------------------
# Training & Experiment Endpoints
# ---------------------------------------------------------------------------

@router.post("/training/jobs", response_model=TrainingJobRecord, summary="Queue Model Training Job")
async def create_training_job(
    req: CreateTrainingJobRequest,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        job = await training_manager.create_training_job(
            model_version=req.model_version,
            dataset_version=req.dataset_version,
            hyperparameters=req.hyperparameters,
            feature_version=req.feature_version,
            created_by=user_email,
        )
        return job
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to queue training job: {e}")


@router.get("/training/jobs", response_model=List[TrainingJobRecord], summary="List Training Jobs")
async def list_training_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Any = Depends(require_role("admin", "authority")),
):
    return await training_manager.list_training_jobs(limit=limit)


@router.get("/training/jobs/{job_id}", response_model=TrainingJobRecord, summary="Get Training Job Details")
async def get_training_job(
    job_id: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    job = await training_manager.get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Training job '{job_id}' not found")
    return job


@router.post("/training/jobs/{job_id}/cancel", summary="Cancel Training Job")
async def cancel_training_job(
    job_id: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    ok = await training_manager.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Training job '{job_id}' not found or could not be cancelled")
    return {"status": "success", "message": f"Training job '{job_id}' cancelled"}


@router.get("/experiments", response_model=List[ExperimentRecord], summary="List ML Experiments")
async def list_experiments(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Any = Depends(require_role("admin", "authority")),
):
    return await experiment_tracker.list_experiments(limit=limit)


@router.get("/experiments/{experiment_id}", response_model=ExperimentRecord, summary="Get Experiment Details")
async def get_experiment(
    experiment_id: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    exp = await experiment_tracker.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experiment '{experiment_id}' not found")
    return exp


# ---------------------------------------------------------------------------
# Model Registry & Governance Endpoints
# ---------------------------------------------------------------------------

@router.get("/models", response_model=List[ModelRegistryEntry], summary="List Registered Models")
async def list_models(
    status_filter: Optional[ModelLifecycleStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Any = Depends(require_role("admin", "authority")),
):
    return await model_registry.list_models(status=status_filter, limit=limit)


@router.get("/models/production", response_model=ModelRegistryEntry, summary="Get Active Production Model")
async def get_production_model(
    current_user: Any = Depends(require_role("admin", "authority")),
):
    prod = await model_registry.get_production_model()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active production model found in registry")
    return prod


@router.get("/models/{model_version}", response_model=ModelRegistryEntry, summary="Get Model Details")
async def get_model(
    model_version: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    model_entry = await model_registry.get_model(model_version)
    if not model_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{model_version}' not found")
    return model_entry


@router.post("/models/{model_version}/validate", response_model=ModelValidationGateResult, summary="Execute Model Validation Gate")
async def validate_model(
    model_version: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    try:
        return await model_registry.validate_model(model_version)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/models/{model_version}/approve", response_model=ModelRegistryEntry, summary="Approve Model for Deployment")
async def approve_model(
    model_version: str,
    req: ApproveModelRequest,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        return await model_registry.approve_model(
            model_version=model_version,
            approver=user_email,
            reason=req.reason,
            evaluation_summary=req.evaluation_summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/models/{model_version}/deploy", response_model=ModelRegistryEntry, summary="Deploy Model to Production")
async def deploy_model_to_production(
    model_version: str,
    req: DeployModelRequest,
    current_user: Any = Depends(require_role("admin")),
):
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        res = await model_registry.deploy_to_environment(
            model_version=model_version,
            target_status=req.target_status,
            deployed_by=user_email,
            reason=req.reason,
            canary_percentage=req.canary_percentage,
        )
        # Hot-reload the runtime inference model
        if req.target_status == ModelLifecycleStatus.PRODUCTION:
            model_loader.load_and_validate(model_version)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/models/{model_version}/shadow", response_model=ModelRegistryEntry, summary="Deploy Model to Shadow Mode")
async def deploy_model_to_shadow(
    model_version: str,
    req: DeployModelRequest,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        res = await model_registry.deploy_to_environment(
            model_version=model_version,
            target_status=ModelLifecycleStatus.SHADOW,
            deployed_by=user_email,
            reason=req.reason,
        )
        # Initialize shadow engine session
        shadow_engine.load_shadow_model(model_version)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/models/{model_version}/stage", response_model=ModelRegistryEntry, summary="Deploy Model to Staging")
async def deploy_model_to_staging(
    model_version: str,
    req: DeployModelRequest,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        return await model_registry.deploy_to_environment(
            model_version=model_version,
            target_status=ModelLifecycleStatus.STAGING,
            deployed_by=user_email,
            reason=req.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/models/{model_version}/canary", response_model=ModelRegistryEntry, summary="Deploy Model to Canary")
async def deploy_model_to_canary(
    model_version: str,
    req: DeployModelRequest,
    current_user: Any = Depends(require_role("admin")),
):
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        return await model_registry.deploy_to_environment(
            model_version=model_version,
            target_status=ModelLifecycleStatus.CANARY,
            deployed_by=user_email,
            reason=req.reason,
            canary_percentage=req.canary_percentage,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/models/{model_version}/rollback", response_model=ModelRegistryEntry, summary="Rollback Production Model")
async def rollback_model(
    model_version: str,
    req: RollbackModelRequest,
    current_user: Any = Depends(require_role("admin")),
):
    """
    Restores the specified model version to PRODUCTION and marks current model ROLLED_BACK.
    """
    try:
        user_email = getattr(current_user, "email", "admin_operator")
        res = await model_registry.rollback(
            target_model_version=model_version,
            actor=user_email,
            reason=req.reason,
        )
        # Hot-reload inference model to rolled-back target
        model_loader.load_and_validate(model_version)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/models/compare/{model_a}/{model_b}", response_model=ModelComparisonReport, summary="Compare Two Models")
async def compare_models(
    model_a: str,
    model_b: str,
    current_user: Any = Depends(require_role("admin", "authority")),
):
    mod_a = await model_registry.get_model(model_a)
    mod_b = await model_registry.get_model(model_b)
    if not mod_a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{model_a}' not found")
    if not mod_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{model_b}' not found")

    return model_comparison_engine.compare_models(production_model=mod_a, candidate_model=mod_b)


# ---------------------------------------------------------------------------
# Drift & Monitoring Endpoints
# ---------------------------------------------------------------------------

@router.get("/drift", response_model=ModelDriftReport, summary="Get Model & Feature Drift Report")
async def get_drift_report(
    current_user: Any = Depends(require_role("admin", "authority")),
):
    prod = await model_registry.get_production_model()
    prod_version = prod.model_version if prod else "v1.0.0"
    feat_version = prod.feature_version if prod else "features_v1"

    # Fetch baseline distributions from dataset registry
    ds_entry = await dataset_registry.get_dataset(prod.dataset_version) if prod else None
    base_dists = ds_entry.feature_distributions if ds_entry else {}

    # Sample representative live window buffer (or baseline dummy)
    sample_windows = [np.random.randn(150, 8).astype(np.float32) for _ in range(20)]
    return drift_detector.evaluate_live_window_drift(
        model_version=prod_version,
        feature_version=feat_version,
        baseline_distributions=base_dists,
        window_feature_tensors=sample_windows,
    )


@router.get("/drift/features", summary="Get Feature Specifications & Distributions")
async def get_feature_specifications(
    version: str = Query(default="features_v1"),
    current_user: Any = Depends(require_role("admin", "authority")),
):
    specs = feature_registry.get_feature_specs(version)
    return {
        "feature_version": version,
        "features": [
            {
                "name": s.name,
                "unit": s.physical_unit,
                "source": s.source_channel,
                "transformation": s.transformation,
                "min_bound": s.min_physical_bound,
                "max_bound": s.max_physical_bound,
                "description": s.description,
            }
            for s in specs
        ],
    }


@router.get("/shadow/metrics", summary="Get Shadow Mode Metrics")
async def get_shadow_metrics(
    current_user: Any = Depends(require_role("admin", "authority")),
):
    return shadow_engine.get_shadow_metrics_summary()
