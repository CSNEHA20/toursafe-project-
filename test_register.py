import sys
sys.path.insert(0, "backend")
from unittest.mock import MagicMock, PropertyMock
from fastapi.testclient import TestClient
from app.main import app

# Patch the module-level get_database - make it return an async mock
import app.core.database as db_module

# Create an async mock that returns a mock database when called
mock_db = MagicMock()
# Make find_one, insert_one, update_one async-compatible (return None immediately)
mock_db["users"].find_one = MagicMock(return_value=None)
mock_db["users"].insert_one = MagicMock(return_value=None)
mock_db["users"].update_one = MagicMock(return_value=None)
mock_db["tourists"].find_one = MagicMock(return_value=None)
mock_db["tourists"].insert_one = MagicMock(return_value=None)
mock_db["authority"].find_one = MagicMock(return_value=None)
mock_db["authority"].insert_one = MagicMock(return_value=None)

# Make get_database return a coroutine that resolves to mock_db
async def mock_get_database():
    return mock_db

# Replace the function
db_module.get_database = mock_get_database

# Also patch in main module
import app.main as main_module
main_module.get_database = mock_get_database

# Create TestClient
client = TestClient(app)

# Test registration
resp = client.post("/api/v1/auth/register", json={
    "email": "test@example.com",
    "password": "testpass123",
    "full_name": "Test",
    "role": "tourist"
})
print("Register status:", resp.status_code)
print("Register body:", resp.json())