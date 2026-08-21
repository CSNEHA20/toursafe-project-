import pytest
import sys
import copy
from typing import Any, Dict, List

sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from app.main import app
import app.core.database as db_module
from app.core.database import init_db_indexes
import app.routers.zones as zones_router
import app.routers.authority_zones as authority_zones_router
from app.core.security import create_access_token
from app.models.zone import ZoneType, ZoneRiskLevel, ZoneStatus, ZoneAuditAction
from app.core.geo_validation import (
    validate_coordinate_pair,
    validate_point_geometry,
    validate_polygon_geometry,
    validate_zone_geometry,
    compute_polygon_center,
    GeoValidationError,
)
from app.services.seed_zones import INITIAL_DEV_ZONES, seed_initial_zones


# In-memory mock collection for async testing
class MockMongoCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if k == "$or":
                sub_matches = any(self._matches(doc, sub) for sub in v)
                if not sub_matches:
                    return False
            elif isinstance(v, dict):
                if "$regex" in v:
                    pattern = v["$regex"].lstrip("^").rstrip("$")
                    val = str(doc.get(k, ""))
                    ignore_case = v.get("$options") == "i"
                    if ignore_case:
                        if pattern.lower() not in val.lower():
                            return False
                    else:
                        if pattern not in val:
                            return False
                elif "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def find_one(self, filter_dict=None, *args, **kwargs):
        if not filter_dict:
            return copy.deepcopy(self.docs[0]) if self.docs else None
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict=None, *args, **kwargs):
        filtered = []
        filter_dict = filter_dict or {}
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                filtered.append(copy.deepcopy(doc))
        
        class Cursor:
            def __init__(self, items):
                self.items = items
                self._skip = 0
                self._limit = len(items)

            def sort(self, key, direction=1):
                reverse = direction == -1
                self.items.sort(key=lambda x: str(x.get(key, "")), reverse=reverse)
                return self

            def skip(self, n):
                self._skip = n
                return self

            def limit(self, n):
                self._limit = n
                return self

            async def to_list(self, length=None):
                limit_val = self._limit if length is None else length
                return self.items[self._skip : self._skip + limit_val]

        return Cursor(filtered)

    async def insert_one(self, document):
        doc = copy.deepcopy(document)
        if "id" not in doc:
            doc["id"] = f"id_{len(self.docs) + 1}"
        if "_id" not in doc:
            doc["_id"] = doc["id"]
        self.docs.append(doc)
        return type("Obj", (), {"inserted_id": doc["id"]})()

    async def update_one(self, filter_dict, update_dict, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

    async def delete_one(self, filter_dict):
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                del self.docs[idx]
                return type("Obj", (), {"deleted_count": 1})()
        return type("Obj", (), {"deleted_count": 0})()

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        count = sum(1 for doc in self.docs if self._matches(doc, filter_dict))
        return count

    async def create_index(self, *args, **kwargs):
        return "index_created"


class MockAppDatabase:
    def __init__(self):
        self.zones = MockMongoCollection("zones")
        self.zone_audits = MockMongoCollection("zone_audits")
        self.users = MockMongoCollection("users")
        self.tourists = MockMongoCollection("tourists")
        self.authority = MockMongoCollection("authority")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockMongoCollection(name))
        return getattr(self, name)

    async def command(self, *args, **kwargs):
        return {"ok": 1}


global_mock_db = MockAppDatabase()


def reset_mock_db():
    global_mock_db.zones.docs = [copy.deepcopy(z) for z in INITIAL_DEV_ZONES]
    global_mock_db.zone_audits.docs = []


reset_mock_db()

# Direct patch on router modules
db_module.get_database = lambda: global_mock_db
zones_router.get_database = lambda: global_mock_db
authority_zones_router.get_database = lambda: global_mock_db

app.dependency_overrides[db_module.get_database] = lambda: global_mock_db
app.dependency_overrides[zones_router.get_database] = lambda: global_mock_db
app.dependency_overrides[authority_zones_router.get_database] = lambda: global_mock_db


@pytest.fixture(autouse=True)
def setup_each_test():
    reset_mock_db()
    app.dependency_overrides[db_module.get_database] = lambda: global_mock_db
    app.dependency_overrides[zones_router.get_database] = lambda: global_mock_db
    app.dependency_overrides[authority_zones_router.get_database] = lambda: global_mock_db


@pytest.fixture
def auth_headers_authority():
    token = create_access_token("auth_user_001", "authority")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_tourist():
    token = create_access_token("tourist_user_001", "tourist")
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# 1. GEOJSON GEOMETRY & VALIDATION TESTS
# ============================================================

class TestGeoJSONValidation:
    def test_valid_point_coordinate_order(self):
        # [longitude, latitude] -> 77.4892 lon, 10.2381 lat
        lon, lat = validate_coordinate_pair([77.4892, 10.2381])
        assert lon == 77.4892
        assert lat == 10.2381

    def test_point_out_of_bounds_latitude(self):
        with pytest.raises(GeoValidationError, match="latitude 95.0 out of range"):
            validate_coordinate_pair([77.4892, 95.0])

        with pytest.raises(GeoValidationError, match="latitude -95.0 out of range"):
            validate_coordinate_pair([77.4892, -95.0])

    def test_point_out_of_bounds_longitude(self):
        with pytest.raises(GeoValidationError, match="longitude 185.0 out of range"):
            validate_coordinate_pair([185.0, 10.2381])

        with pytest.raises(GeoValidationError, match="longitude -190.0 out of range"):
            validate_coordinate_pair([-190.0, 10.2381])

    def test_valid_polygon(self):
        poly = {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.48, 10.23],
                    [77.49, 10.23],
                    [77.49, 10.24],
                    [77.48, 10.24],
                    [77.48, 10.23],
                ]
            ],
        }
        res = validate_polygon_geometry(poly)
        assert res["type"] == "Polygon"
        assert len(res["coordinates"][0]) == 5

    def test_polygon_unclosed_ring_rejected(self):
        unclosed = {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.48, 10.23],
                    [77.49, 10.23],
                    [77.49, 10.24],
                    [77.48, 10.24],  # missing closure to [77.48, 10.23]
                ]
            ],
        }
        with pytest.raises(GeoValidationError, match="linear ring must be closed"):
            validate_polygon_geometry(unclosed)

    def test_polygon_fewer_than_four_points_rejected(self):
        too_few = {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.48, 10.23],
                    [77.49, 10.23],
                    [77.48, 10.23],
                ]
            ],
        }
        with pytest.raises(GeoValidationError, match="at least 4 coordinate positions"):
            validate_polygon_geometry(too_few)

    def test_compute_polygon_center(self):
        poly = {
            "type": "Polygon",
            "coordinates": [
                [
                    [10.0, 20.0],
                    [30.0, 20.0],
                    [30.0, 40.0],
                    [10.0, 40.0],
                    [10.0, 20.0],
                ]
            ],
        }
        center = compute_polygon_center(poly)
        assert center["type"] == "Point"
        assert center["coordinates"] == [20.0, 30.0]


# ============================================================
# 2. TOURIST ZONES API TESTS
# ============================================================

class TestTouristZoneEndpoints:
    def test_get_active_zones_returns_map_ready_payload(self):
        client = TestClient(app)
        response = client.get("/api/v1/zones")
        assert response.status_code == 200
        data = response.json()
        assert "zones" in data
        assert data["total"] >= 8
        first = data["zones"][0]
        assert "zone_id" in first
        assert "geometry" in first
        assert first["geometry"]["type"] == "Polygon"
        assert "center" in first
        assert first["center"]["type"] == "Point"
        assert "type" in first  # mapped from zone_type
        assert "risk_level" in first

    def test_filter_zones_by_type(self):
        client = TestClient(app)
        response = client.get("/api/v1/zones?zone_type=restricted")
        assert response.status_code == 200
        data = response.json()
        for z in data["zones"]:
            assert z["type"] == "restricted"

    def test_get_zone_by_id(self):
        client = TestClient(app)
        response = client.get("/api/v1/zones/zone-kodaikanal-lake")
        assert response.status_code == 200
        data = response.json()
        assert data["zone_id"] == "zone-kodaikanal-lake"
        assert data["name"] == "Kodaikanal Lake & Boat Club Area"

    def test_get_nonexistent_zone_returns_404(self):
        client = TestClient(app)
        response = client.get("/api/v1/zones/nonexistent-zone-xyz")
        assert response.status_code == 404


# ============================================================
# 3. AUTHORITY ZONES CRUD & RBAC TESTS
# ============================================================

class TestAuthorityZonesCRUD:
    def test_tourist_cannot_create_zone(self, auth_headers_tourist):
        client = TestClient(app)
        payload = {
            "name": "Unauthorized Zone",
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[77.48, 10.23], [77.49, 10.23], [77.49, 10.24], [77.48, 10.24], [77.48, 10.23]]],
            },
        }
        response = client.post("/api/v1/authority/zones", json=payload, headers=auth_headers_tourist)
        assert response.status_code == 403

    def test_authority_creates_valid_zone_and_creates_audit_log(self, auth_headers_authority):
        client = TestClient(app)
        payload = {
            "name": "New Silver Cascade Safe Haven",
            "description": "Waterfall safety perimeter and viewing area.",
            "zone_type": "safe",
            "risk_level": "low",
            "status": "active",
            "boundary": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.5100, 10.2500],
                        [77.5200, 10.2500],
                        [77.5200, 10.2400],
                        [77.5100, 10.2400],
                        [77.5100, 10.2500],
                    ]
                ],
            },
            "properties": {"dataset": "DEVELOPMENT GEOMETRY"},
        }
        response = client.post("/api/v1/authority/zones", json=payload, headers=auth_headers_authority)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Silver Cascade Safe Haven"
        assert data["zone_type"] == "safe"
        assert data["center"]["type"] == "Point"

        # Verify audit log created
        audit_resp = client.get(f"/api/v1/authority/zones/{data['id']}/audits", headers=auth_headers_authority)
        assert audit_resp.status_code == 200
        audits = audit_resp.json()
        assert len(audits) >= 1
        assert audits[0]["action"] == "created"

    def test_authority_create_invalid_geojson_rejected(self, auth_headers_authority):
        client = TestClient(app)
        # Unclosed ring
        payload = {
            "name": "Invalid Geo Zone",
            "boundary": {
                "type": "Polygon",
                "coordinates": [[[77.48, 10.23], [77.49, 10.23], [77.49, 10.24], [77.48, 10.24]]],
            },
        }
        response = client.post("/api/v1/authority/zones", json=payload, headers=auth_headers_authority)
        assert response.status_code == 422

    def test_authority_update_zone_risk_and_status(self, auth_headers_authority):
        client = TestClient(app)
        update_payload = {
            "risk_level": "critical",
            "status": "inactive",
            "description": "Temporarily closed due to landslide warning.",
        }
        response = client.patch(
            "/api/v1/authority/zones/zone-kodaikanal-lake",
            json=update_payload,
            headers=auth_headers_authority,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "critical"
        assert data["status"] == "inactive"

        # Check audit entry
        audit_resp = client.get("/api/v1/authority/zones/zone-kodaikanal-lake/audits", headers=auth_headers_authority)
        assert audit_resp.status_code == 200
        audits = audit_resp.json()
        assert len(audits) >= 1
        assert audits[0]["action"] == "status_changed"

    def test_authority_update_boundary_creates_boundary_updated_audit(self, auth_headers_authority):
        client = TestClient(app)
        new_poly = {
            "boundary": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.4800, 10.2400],
                        [77.4990, 10.2400],
                        [77.4990, 10.2300],
                        [77.4800, 10.2300],
                        [77.4800, 10.2400],
                    ]
                ],
            }
        }
        response = client.patch(
            "/api/v1/authority/zones/zone-coakers-walk",
            json=new_poly,
            headers=auth_headers_authority,
        )
        assert response.status_code == 200

        audit_resp = client.get("/api/v1/authority/zones/zone-coakers-walk/audits", headers=auth_headers_authority)
        assert audit_resp.status_code == 200
        audits = audit_resp.json()
        assert audits[0]["action"] == "boundary_updated"

    def test_authority_list_zones_with_search_and_pagination(self, auth_headers_authority):
        client = TestClient(app)
        response = client.get("/api/v1/authority/zones?q=Ooty&limit=2", headers=auth_headers_authority)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) <= 2
        assert all("ooty" in item["name"].lower() for item in data["items"])

    def test_authority_delete_zone_soft_deactivates(self, auth_headers_authority):
        client = TestClient(app)
        response = client.delete("/api/v1/authority/zones/zone-guna-caves", headers=auth_headers_authority)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify it is marked inactive in DB
        zone_resp = client.get("/api/v1/authority/zones/zone-guna-caves", headers=auth_headers_authority)
        assert zone_resp.status_code == 200
        assert zone_resp.json()["status"] == "inactive"
        assert zone_resp.json()["is_active"] is False


# ============================================================
# 4. STARTUP SEEDING & INDEX TESTS
# ============================================================

class TestSeedingAndIndexes:
    @pytest.mark.asyncio
    async def test_seed_initial_zones_idempotent(self):
        db = MockAppDatabase()
        count1 = await seed_initial_zones(db)
        assert count1 == len(INITIAL_DEV_ZONES)
        assert len(db.zones.docs) == len(INITIAL_DEV_ZONES)

        # Re-running returns 0 new additions
        count2 = await seed_initial_zones(db)
        assert count2 == 0
        assert len(db.zones.docs) == len(INITIAL_DEV_ZONES)

    @pytest.mark.asyncio
    async def test_init_db_indexes(self):
        db = MockAppDatabase()
        await init_db_indexes(db)
        assert True
