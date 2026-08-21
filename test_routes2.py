import sys
sys.path.insert(0, "backend")
from app.routers.auth import router as auth_router
from app.routers.tourists import router as tourists_router
from app.routers.authority import router as authority_router
print("Auth prefix:", auth_router.prefix)
print("Tourists prefix:", tourists_router.prefix)
print("Authority prefix:", authority_router.prefix)