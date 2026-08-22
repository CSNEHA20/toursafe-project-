# Problems & Solutions — Prompt 25: Authority Administration, Policy Configuration & System Governance

## 1. Issue: Pydantic Model `use_enum_values` and `.value` Attribute Error
- **Problem**: In `GovernanceConfigurationRecord`, Pydantic's `model_config = {"use_enum_values": True}` serializes enums as primitive strings (`"SAFETY"`), causing `config.type.value` to throw `'str' object has no attribute 'value'`.
- **Solution**: Handled both string values and Enum instances gracefully: `config.type if isinstance(config.type, str) else config.type.value`.

## 2. Issue: MockCollection `find_one` Positional Projection vs Sort Argument
- **Problem**: PyMongo's `find_one` accepts `find_one(filter, projection, sort=...)`. The test mock collection initially had `find_one(self, filter_dict=None, sort=None, *args, **kwargs)`, causing the second positional argument (projection dictionary `{"_id": 0}`) to be received as `sort`, leading to a `KeyError: 0`.
- **Solution**: Updated `MockCollection.find_one` signature to `find_one(self, filter_dict=None, projection=None, sort=None, *args, **kwargs)` and added proper field projection stripping.

## 3. Issue: Event Loop Closed in Pytest Asyncio Proactor Loops
- **Problem**: When pytest ran async tests against global database connections without mocking, subsequent test cases inherited closed event loops from prior test fixtures in Windows Python 3.14.
- **Solution**: Standardized the mock database engine fixture (`MockDatabase` with autouse fixture) matching the repository's established pattern in `test_response_orchestration.py`.
