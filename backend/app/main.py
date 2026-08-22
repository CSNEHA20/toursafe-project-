from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core import database as db_core
from .core import redis as redis_core
from .services.seed_zones import seed_initial_zones
from .routers.auth import router as auth_router
from .routers.tourists import router as tourists_router
from .routers.authority import router as authority_router
from .routers.kyc_documents import router as kyc_router
from .routers.medical import router as medical_router
from .routers.emergency_contacts import router as emergency_contacts_router
from .routers.itineraries import router as itineraries_router
from .routers.zones import router as zones_router
from .routers.authority_zones import router as authority_zones_router
from .routers.geofence import router as geofence_router
from .routers.health import router as health_router
from .routers.realtime import router as realtime_router
from .routers.dev_realtime import router as dev_realtime_router
from .routers.location import router as location_router
from .routers.imu import router as imu_router
from .routers.telemetry import router as telemetry_router
from .routers.ml import router as ml_router
from .routers.safety import router as safety_router
from .routers.emergency import router as emergency_router
from .routers.responders import router as responders_router
from .routers.notifications import router as notifications_router
from .routers.analytics import router as analytics_router
from .routers.ml_lifecycle import router as ml_lifecycle_router
from .routers.identity import router as identity_router
from .routers.kyc import router as kyc_platform_router
from .routers.credentials import router as credentials_router
from .services.ml.engine import ml_inference_engine
from .services.safety import safety_repository
from .ml.lifecycle import dataset_registry, model_registry, training_manager, experiment_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        db = db_core.get_database()
        await db.command("ping")
        print("✅ MongoDB connection verified on startup")
        await db_core.init_db_indexes(db)
        await safety_repository.init_indexes()
        await dataset_registry.init_indexes()
        await model_registry.init_indexes()
        await training_manager.init_indexes()
        await experiment_tracker.init_indexes()
        seeded = await seed_initial_zones(db)
        if seeded > 0:
            print(f"✅ Successfully seeded {seeded} initial development geospatial zones")
    except Exception as e:
        print(f"⚠️  MongoDB startup initialization note: {e}")

    try:
        await redis_core.get_redis_client()
    except Exception as e:
        print(f"⚠️  Redis startup initialization note: {e}")

    # Initialize ML Inference Engine
    try:
        await ml_inference_engine.start()
    except Exception as e:
        print(f"⚠️  ML Inference Engine initialization note: {e}")

    yield

    # Shutdown
    try:
        await ml_inference_engine.stop()
    except Exception as e:
        print(f"⚠️  ML Inference Engine shutdown note: {e}")
    await redis_core.close_redis()
    await db_core.close_database()


app = FastAPI(
    title="TourSafe Backend",
    description="TourSafe Application Backend - FastAPI + MongoDB",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration - environment-based allowed origins
allowed_origins = settings.cors_origins if settings.cors_origins else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Set-Cookie", "Accept"],
)

app.include_router(health_router)
app.include_router(realtime_router)
app.include_router(dev_realtime_router)
app.include_router(location_router)
app.include_router(imu_router)
app.include_router(telemetry_router)
app.include_router(ml_router)
app.include_router(auth_router)
app.include_router(tourists_router)
app.include_router(authority_router)
app.include_router(kyc_router)
app.include_router(medical_router)
app.include_router(emergency_contacts_router)
app.include_router(itineraries_router)
app.include_router(geofence_router)
app.include_router(zones_router)
app.include_router(authority_zones_router)
app.include_router(emergency_router)
app.include_router(responders_router)
app.include_router(safety_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(ml_lifecycle_router)
app.include_router(identity_router)
app.include_router(kyc_platform_router)
app.include_router(credentials_router)