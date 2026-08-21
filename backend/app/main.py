from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.database import get_database, close_database
from .routers.auth import router as auth_router
from .routers.tourists import router as tourists_router
from .routers.authority import router as authority_router

app = FastAPI(
    title="TourSafe Backend",
    description="TourSafe Application Backend - FastAPI + MongoDB",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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


@app.on_event("startup")
async def startup():
    # Verify MongoDB connection on startup
    try:
        db = get_database()
        await db.command("ping")
        print("✅ MongoDB connection verified on startup")
    except Exception as e:
        print(f"⚠️  MongoDB connection failed on startup: {e}")


@app.on_event("shutdown")
async def shutdown():
    await close_database()


app.include_router(auth_router)
app.include_router(tourists_router)
app.include_router(authority_router)