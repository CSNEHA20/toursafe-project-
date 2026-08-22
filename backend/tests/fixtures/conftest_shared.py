"""
TourSafe QA — Shared Test Fixtures
===================================
Deterministic in-memory mocks for MongoDB, Redis, and external providers.
Used across unit, integration, and regression test suites.

All identities are synthetic. No real PII is used.
"""

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ============================================================
# DETERMINISTIC TEST CONSTANTS
# ============================================================

TEST_EPOCH = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
TEST_GPS_LAT = 15.2993
TEST_GPS_LON = 74.1240
TEST_GPS_ALT = 15.0

# Test Identity IDs — deterministic, synthetic
TOURIST_USER_ID = "user_tourist_001"
TOURIST_ID = "tourist_qa_001"
TOURIST_USER_ID_2 = "user_tourist_002"
TOURIST_ID_2 = "tourist_qa_002"

RESPONDER_USER_ID = "user_responder_001"
RESPONDER_ID = "responder_qa_001"

AUTH_OP_USER_ID = "user_auth_op_001"
AUTH_ADMIN_USER_ID = "user_auth_admin_001"
SYS_ADMIN_USER_ID = "user_sys_admin_001"
PRIVACY_ADMIN_USER_ID = "user_privacy_001"
AUDITOR_USER_ID = "user_auditor_001"
AUTH_B_USER_ID = "user_auth_b_001"

JURISDICTION_A_ID = "jurisdiction_alpha"
JURISDICTION_B_ID = "jurisdiction_beta"

ZONE_SAFE_ID = "zone_safe_001"
ZONE_DANGER_ID = "zone_danger_001"

INCIDENT_ID = "incident_qa_001"
SOS_ID = "sos_qa_001"
NOTIFICATION_ID = "notif_qa_001"
ASSIGNMENT_ID = "assignment_qa_001"


# ============================================================
# IN-MEMORY MONGODB COLLECTION MOCK
# ============================================================

class MockCollection:
    """
    Async-compatible in-memory MongoDB collection mock.
    Supports: insert_one, find_one, find, update_one, replace_one,
    delete_one, delete_many, count_documents, create_index, create_indexes.
    """

    def __init__(self, name: str = "collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for k, v in query.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif k == "$and":
                if not all(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                doc_val = doc.get(k)
                if "$in" in v:
                    if doc_val not in v["$in"]:
                        return False
                elif "$ne" in v:
                    if doc_val == v["$ne"]:
                        return False
                elif "$gt" in v:
                    if not (doc_val is not None and doc_val > v["$gt"]):
                        return False
                elif "$gte" in v:
                    if not (doc_val is not None and doc_val >= v["$gte"]):
                        return False
                elif "$lt" in v:
                    if not (doc_val is not None and doc_val < v["$lt"]):
                        return False
                elif "$lte" in v:
                    if not (doc_val is not None and doc_val <= v["$lte"]):
                        return False
                elif "$exists" in v:
                    exists = k in doc
                    if v["$exists"] != exists:
                        return False
                else:
                    if doc_val != v:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def insert_one(self, doc: Dict[str, Any]):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = d.get("id", f"mock_{self.name}_{len(self.docs)+1}")
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict: Optional[Dict] = None, *args, **kwargs):
        filter_dict = filter_dict or {}
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict: Optional[Dict] = None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matched = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items
                self._skip = 0
                self._limit = None
                self._sort_key = None

            def sort(self, *args, **kwargs):
                return self

            def skip(self, n: int):
                self.items = self.items[n:]
                return self

            def limit(self, n: int):
                self.items = self.items[:n] if n > 0 else self.items
                return self

            def __aiter__(self):
                self._iter = iter(self.items)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

            async def to_list(self, length=None):
                if length:
                    return self.items[:length]
                return self.items

        return AsyncCursor(matched)

    async def update_one(
        self,
        filter_dict: Dict,
        update_dict: Dict,
        upsert: bool = False,
        *args,
        **kwargs,
    ):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                if "$push" in update_dict:
                    for field, value in update_dict["$push"].items():
                        doc.setdefault(field, []).append(copy.deepcopy(value))
                if "$inc" in update_dict:
                    for field, value in update_dict["$inc"].items():
                        doc[field] = doc.get(field, 0) + value
                return type("UpdateResult", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            new_doc.setdefault("_id", new_doc.get("id", f"upsert_{len(self.docs)+1}"))
            self.docs.append(new_doc)
            return type("UpdateResult", (), {
                "modified_count": 0, "matched_count": 0,
                "upserted_id": new_doc.get("id", "new")
            })()
        return type("UpdateResult", (), {"modified_count": 0, "matched_count": 0})()

    async def update_many(self, filter_dict: Dict, update_dict: Dict, *args, **kwargs):
        count = 0
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                count += 1
        return type("UpdateResult", (), {"modified_count": count, "matched_count": count})()

    async def replace_one(self, filter_dict: Dict, replacement: Dict, upsert: bool = False, *args, **kwargs):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                self.docs[i] = copy.deepcopy(replacement)
                return type("UpdateResult", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            self.docs.append(copy.deepcopy(replacement))
            return type("UpdateResult", (), {
                "modified_count": 0, "matched_count": 0,
                "upserted_id": replacement.get("id", "new")
            })()
        return type("UpdateResult", (), {"modified_count": 0, "matched_count": 0})()

    async def delete_one(self, filter_dict: Dict, *args, **kwargs):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                self.docs.pop(i)
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, filter_dict: Dict, *args, **kwargs):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, filter_dict)]
        return type("DeleteResult", (), {"deleted_count": before - len(self.docs)})()

    async def count_documents(self, filter_dict: Optional[Dict] = None, *args, **kwargs):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def create_index(self, *args, **kwargs):
        return "index_created"

    async def create_indexes(self, *args, **kwargs):
        return ["index_created"]

    async def command(self, *args, **kwargs):
        return {"ok": 1}

    async def drop(self):
        self.docs.clear()


# ============================================================
# IN-MEMORY DATABASE MOCK
# ============================================================

class MockDatabase:
    """
    In-memory MongoDB database mock.
    Collections are auto-created on access.
    """

    def __init__(self):
        self._collections: Dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def __getattr__(self, name: str) -> MockCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    async def command(self, cmd: str, *args, **kwargs):
        return {"ok": 1}

    def get_collection(self, name: str) -> MockCollection:
        return self[name]

    def reset(self):
        """Reset all collections."""
        self._collections.clear()

    def seed_test_identities(self):
        """Seed standard test identities."""
        from app.core.security import get_password_hash

        # Tourists
        self["users"].docs.append({
            "id": TOURIST_USER_ID,
            "_id": TOURIST_USER_ID,
            "email": "tourist_qa@toursafe.test",
            "role": "tourist",
            "is_active": True,
            "full_name": "QA Test Tourist",
            "hashed_password": get_password_hash("TestPass123!"),
        })
        self["tourists"].docs.append({
            "id": TOURIST_ID,
            "_id": TOURIST_ID,
            "user_id": TOURIST_USER_ID,
            "full_name": "QA Test Tourist",
            "email": "tourist_qa@toursafe.test",
            "is_active": True,
            "nationality": "IN",
        })

        # Second tourist (for IDOR tests)
        self["users"].docs.append({
            "id": TOURIST_USER_ID_2,
            "_id": TOURIST_USER_ID_2,
            "email": "tourist_qa2@toursafe.test",
            "role": "tourist",
            "is_active": True,
            "full_name": "QA Test Tourist 2",
            "hashed_password": get_password_hash("TestPass123!"),
        })
        self["tourists"].docs.append({
            "id": TOURIST_ID_2,
            "_id": TOURIST_ID_2,
            "user_id": TOURIST_USER_ID_2,
            "full_name": "QA Test Tourist 2",
            "email": "tourist_qa2@toursafe.test",
            "is_active": True,
            "nationality": "IN",
        })

        # Responder
        self["users"].docs.append({
            "id": RESPONDER_USER_ID,
            "_id": RESPONDER_USER_ID,
            "email": "responder_qa@toursafe.test",
            "role": "responder",
            "is_active": True,
            "full_name": "QA Responder",
            "hashed_password": get_password_hash("TestPass123!"),
        })

        # Authority operator
        self["users"].docs.append({
            "id": AUTH_OP_USER_ID,
            "_id": AUTH_OP_USER_ID,
            "email": "auth_op_qa@toursafe.test",
            "role": "authority",
            "is_active": True,
            "full_name": "QA Authority Operator",
            "hashed_password": get_password_hash("TestPass123!"),
        })
        self["authority"].docs.append({
            "id": AUTH_OP_USER_ID,
            "_id": AUTH_OP_USER_ID,
            "user_id": AUTH_OP_USER_ID,
            "full_name": "QA Authority Operator",
            "email": "auth_op_qa@toursafe.test",
            "role": "authority",
            "jurisdiction_id": JURISDICTION_A_ID,
            "organization_name": "QA Police Department",
            "phone": "+911234567890",
            "is_active": True,
        })

        # Authority admin
        self["users"].docs.append({
            "id": AUTH_ADMIN_USER_ID,
            "_id": AUTH_ADMIN_USER_ID,
            "email": "auth_admin_qa@toursafe.test",
            "role": "authority",
            "is_active": True,
            "full_name": "QA Authority Admin",
            "hashed_password": get_password_hash("TestPass123!"),
        })

        return self


# ============================================================
# DETERMINISTIC TELEMETRY FIXTURES
# ============================================================

def make_telemetry_sample(
    lat: float = TEST_GPS_LAT,
    lon: float = TEST_GPS_LON,
    alt: float = TEST_GPS_ALT,
    accel_x: float = 0.1,
    accel_y: float = 0.0,
    accel_z: float = 9.8,
    gyro_x: float = 0.01,
    gyro_y: float = 0.01,
    gyro_z: float = 0.01,
    timestamp: Optional[str] = None,
    sequence: int = 1,
) -> Dict[str, Any]:
    """Create a deterministic telemetry sample payload."""
    ts = timestamp or TEST_EPOCH.isoformat()
    return {
        "type": "full",
        "sequence_number": sequence,
        "device_timestamp": ts,
        "gps": {
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "accuracy": 5.0,
            "speed": 1.0,
            "heading": 90.0,
            "timestamp": ts,
        },
        "accelerometer": {
            "x": accel_x,
            "y": accel_y,
            "z": accel_z,
            "timestamp": ts,
        },
        "gyroscope": {
            "x": gyro_x,
            "y": gyro_y,
            "z": gyro_z,
            "timestamp": ts,
        },
    }


def make_anomalous_telemetry_sequence(n: int = 5) -> List[Dict[str, Any]]:
    """Create a sequence of telemetry samples with high-motion (fall-like) signature."""
    samples = []
    for i in range(n):
        samples.append(make_telemetry_sample(
            accel_x=15.0 + i * 0.5,   # high x-acceleration (fall)
            accel_y=-12.0,              # sharp y-deceleration
            accel_z=2.0,                # near-zero vertical G
            gyro_x=3.0,                 # rapid rotation
            gyro_y=2.5,
            gyro_z=4.0,
            sequence=i + 1,
        ))
    return samples


def make_safe_telemetry_sequence(n: int = 5) -> List[Dict[str, Any]]:
    """Create a sequence of normal walking telemetry samples."""
    samples = []
    for i in range(n):
        samples.append(make_telemetry_sample(
            accel_x=0.05,
            accel_y=0.05,
            accel_z=9.81,
            gyro_x=0.01,
            gyro_y=0.01,
            gyro_z=0.01,
            sequence=i + 1,
        ))
    return samples


# ============================================================
# GPS TEST COORDINATES
# ============================================================

# Inside safe zone
GPS_SAFE_ZONE = {"latitude": 15.2993, "longitude": 74.1240}

# Inside danger zone
GPS_DANGER_ZONE = {"latitude": 15.3100, "longitude": 74.1300}

# Outside all zones
GPS_OUTSIDE_ALL = {"latitude": 15.0000, "longitude": 73.0000}

# Invalid coordinates
GPS_INVALID_LAT = {"latitude": 95.0, "longitude": 74.1240}  # lat > 90
GPS_INVALID_LON = {"latitude": 15.2993, "longitude": 185.0}  # lon > 180
GPS_ZERO = {"latitude": 0.0, "longitude": 0.0}

# Impossible jump (teleportation)
GPS_JUMP_A = {"latitude": 15.2993, "longitude": 74.1240}
GPS_JUMP_B = {"latitude": 28.6448, "longitude": 77.2167}  # Delhi — ~1800km in 1 second


# ============================================================
# SAFE ZONE FIXTURE
# ============================================================

def make_safe_zone(zone_id: str = ZONE_SAFE_ID) -> Dict[str, Any]:
    """Create a deterministic safe zone polygon."""
    return {
        "id": zone_id,
        "zone_name": "QA Safe Beach Zone",
        "zone_type": "safe",
        "risk_level": "safe",
        "is_active": True,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [74.1200, 15.2950],
                [74.1280, 15.2950],
                [74.1280, 15.3030],
                [74.1200, 15.3030],
                [74.1200, 15.2950],
            ]]
        },
    }


def make_danger_zone(zone_id: str = ZONE_DANGER_ID) -> Dict[str, Any]:
    """Create a deterministic danger zone polygon."""
    return {
        "id": zone_id,
        "zone_name": "QA Danger Ravine Zone",
        "zone_type": "danger",
        "risk_level": "danger",
        "is_active": True,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [74.1260, 15.3060],
                [74.1360, 15.3060],
                [74.1360, 15.3140],
                [74.1260, 15.3140],
                [74.1260, 15.3060],
            ]]
        },
    }
