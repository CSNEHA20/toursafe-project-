from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.database import get_database, close_database, init_db_indexes
from .core.redis import get_redis_client, close_redis
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
from .routers.health import router as health_router
from .routers.realtime import router as realtime_router
from .routers.dev_realtime import router as dev_realtime_router
from .routers.location import router as location_router
from .routers.imu import router as imu_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        db = get_database()
        await db.command("ping")
        print("✅ MongoDB connection verified on startup")
        await init_db_indexes(db)
        seeded = await seed_initial_zones(db)
        if seeded > 0:
            print(f"✅ Successfully seeded {seeded} initial development geospatial zones")
    except Exception as e:
        print(f"⚠️  MongoDB startup initialization note: {e}")

    try:
        await get_redis_client()
    except Exception as e:
        print(f"⚠️  Redis startup initialization note: {e}")

    yield

    # Shutdown
    await close_redis()
    await close_database()


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
app.include_router(auth_router)
app.include_router(tourists_router)
app.include_router(authority_router)
app.include_router(kyc_router)
app.include_router(medical_router)
app.include_router(emergency_contacts_router)
app.include_router(itineraries_router)
app.include_router(zones_router)
app.include_router(authority_zones_router)