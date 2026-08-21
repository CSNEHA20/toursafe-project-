import sys
sys.path.insert(0, "backend")
from app.routers.auth import router as auth_router
print("Auth router routes:")
for route in auth_router.routes:
    print("  ", getattr(route, "path", "?"))