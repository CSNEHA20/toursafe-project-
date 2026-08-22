# Architectural Decisions: Prompt 27

## Decision 1: Decision-Support Only / Zero Autonomous Side Effects
- **Context**: Allowing an LLM to directly dispatch police, ambulances, or modify risk zones risks critical operational failures or hallucinations.
- **Decision**: Every state-altering operation MUST return a structured `ActionProposal` with preview parameters, expected effect, reason, and a cryptographically secure confirmation token (`tok_...`). Execution only occurs when an authorized human operator submits a signed confirmation request.

## Decision 2: Pluggable LLM Provider with Deterministic Agentic Fallback
- **Context**: CI/CD and offline testing environments do not have live Gemini/OpenAI API keys or network access.
- **Decision**: Implemented `DeterministicAgenticProvider` alongside `GeminiProvider`, `OpenAIProvider`, and `BedrockProvider`. The deterministic provider parses intent, triggers real tool functions, and generates live database-grounded answers and action preview proposals identically to production LLMs without requiring external network calls.

## Decision 3: Mandatory PII Redaction at the Tool Layer
- **Context**: LLM context windows or conversation logs should never leak raw personal information of tourists.
- **Decision**: Implemented `_sanitize_pii()` directly in `tools.py` to mask phone numbers, emails, and passport/KYC IDs before records ever enter the prompt or response payloads.
