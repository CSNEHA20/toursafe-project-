# Problems and Solutions: Prompt 27

## Problem 1: Pytest AsyncIO Event Loop Closed Error with Motor MongoDB
- **Symptom**: Integration tests threw `RuntimeError: Event loop is closed` when executing async MongoDB calls across multiple test cases.
- **Cause**: Pytest-asyncio creates and destroys event loops per test function, whereas Motor database client pools retain connection sockets bound to the initial event loop.
- **Solution**: Created `app.services.copilot.test_utils.setup_mock_db` with `MockDatabase` providing scoped in-memory collections supporting query filtering, sorting, cursor iteration, and atomic `$set`/`$inc` updates.

## Problem 2: Retired SOP Document Retrieval in RAG
- **Symptom**: Keyword queries could match outdated legacy standard operating procedures.
- **Cause**: Standard vector search or keyword overlap doesn't distinguish document lifecycle status.
- **Solution**: Added strict pre-filtering in `rag_service.search()` to filter for `status == "active"` and match the authority's `jurisdiction_id` or universal docs by default.

## Problem 3: Multi-Tool Infinite Loops
- **Symptom**: LLM could potentially loop on identical tool calls if results did not immediately satisfy termination criteria.
- **Cause**: Autonomous agent loops need bounded iteration control.
- **Solution**: Enforced a hard limit of `settings.copilot_max_tool_calls_per_turn` (default: 5) and duplicate call hash detection in `copilot_service.py`.
