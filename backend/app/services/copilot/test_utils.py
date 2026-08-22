"""
TourSafe Test Helper: In-memory MockDatabase implementation for async testing.
Provides mock MongoDB collections with support for queries, sorting, pagination,
indexes, and atomic updates.
"""

import copy
import re
from typing import Any, Dict, List, Optional
import pytest
from ...core import database as d_mod


class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$in" in v:
                    if val not in v["$in"]:
                        return False
                elif "$ne" in v:
                    if val == v["$ne"]:
                        return False
                elif "$gte" in v:
                    if str(val) < str(v["$gte"]):
                        return False
                elif "$lte" in v:
                    if str(val) > str(v["$lte"]):
                        return False
                elif "$regex" in v:
                    pattern = re.compile(v["$regex"], re.IGNORECASE if v.get("$options") == "i" else 0)
                    if not pattern.search(str(val or "")):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def create_index(self, *args, **kwargs):
        return "index_ok"

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [d for d in self.docs if self._matches(d, filter_dict)]
        if not matches:
            return None
        if sort:
            sort_field, sort_order = sort[0]
            matches.sort(key=lambda x: x.get(sort_field, ""), reverse=(sort_order == -1))
        return copy.deepcopy(matches[0])

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items
                self.index = 0

            def sort(self, key, order=1):
                self.items.sort(key=lambda x: str(x.get(key, "")), reverse=(order == -1))
                return self

            def skip(self, n):
                self.items = self.items[n:]
                return self

            def limit(self, n):
                self.items = self.items[:n]
                return self

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.items):
                    item = self.items[self.index]
                    self.index += 1
                    return item
                raise StopAsyncIteration

            async def to_list(self, length=100):
                return self.items[:length]

        return AsyncCursor(matches)

    def aggregate(self, pipeline):
        class AggregateCursor:
            def __init__(self, coll):
                self.coll = coll
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            async def to_list(self, length=100):
                return []

        return AggregateCursor(self)

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def update_one(self, filter_dict, update_dict, upsert=False):
        filter_dict = filter_dict or {}
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(copy.deepcopy(update_dict["$set"]))
                if "$inc" in update_dict:
                    for k, v in update_dict["$inc"].items():
                        d[k] = d.get(k, 0) + v
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            self.docs.append(new_doc)
            return type("UpdateResult", (), {"matched_count": 0, "upserted_id": "new_1"})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    async def update_many(self, filter_dict, update_dict):
        filter_dict = filter_dict or {}
        matched = 0
        for d in self.docs:
            if self._matches(d, filter_dict):
                matched += 1
                if "$set" in update_dict:
                    d.update(copy.deepcopy(update_dict["$set"]))
        return type("UpdateResult", (), {"matched_count": matched, "modified_count": matched})()

    async def delete_one(self, filter_dict):
        filter_dict = filter_dict or {}
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_dict):
                self.docs.pop(i)
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, filter_dict):
        filter_dict = filter_dict or {}
        orig_len = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, filter_dict)]
        return type("DeleteResult", (), {"deleted_count": orig_len - len(self.docs)})()


class MockDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return self[name]


def setup_mock_db(monkeypatch):
    mock_db = MockDatabase()
    monkeypatch.setattr(d_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(d_mod, "database", mock_db)
    return mock_db
