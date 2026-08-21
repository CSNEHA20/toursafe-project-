import sys
sys.path.insert(0, "backend")
from app.main import app
for route in app.routes:
    print(getattr(route, "path", "?"))