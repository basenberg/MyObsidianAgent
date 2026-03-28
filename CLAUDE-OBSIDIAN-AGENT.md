# AI Agent Development Instructions

## Project Overview

OpenAI-compatible API agent for Obsidian CoPilot using FastAPI + Pydantic AI, UV, Ruff + mypy (strict type safety), Structlog (AI-optimized logging), and vertical slice architecture.

## Core Principles

1. **TYPE SAFETY IS NON-NEGOTIABLE**
   - All functions, methods, and variables MUST have type annotations
   - Strict mypy configuration is enforced
   - No `Any` types without explicit justification

2. **KISS** (Keep It Simple, Stupid)
   - Prefer simple, readable solutions over clever abstractions

3. **YAGNI** (You Aren't Gonna Need It)
   - Don't build features until they're actually needed

**Architecture:**

```
src/
├── agent/    # Core orchestration
├── openai/   # OpenAI compatibility layer
├── tools/    # Independent slices (web_search, image_analysis, etc.)
└── shared/   # Cross-cutting (config, logging, middleware)
```

Each tool is a vertical slice containing tool.py, schemas.py, service.py.

---

## Documentation Style

**Use Google-style docstrings** for all functions, classes, and modules:

```python
def process_request(user_id: str, query: str) -> dict[str, Any]:
    """Process a user request and return results.

    Args:
        user_id: Unique identifier for the user.
        query: The search query string.

    Returns:
        Dictionary containing results and metadata.

    Raises:
        ValueError: If query is empty or invalid.
        ProcessingError: If processing fails after retries.
    """
```

---

## Logging Rules

**Philosophy:** Logs are optimized for AI agent consumption. Include enough context for an LLM to understand and fix issues without human intervention.

### Required (MUST)

1. **Import shared logger:** `from src.shared.logging import get_logger; logger = get_logger(__name__)`

2. **Use appropriate levels:** `debug` (diagnostics), `info` (operations), `warning` (recoverable), `error` (non-fatal), `exception` (in except blocks with stack traces)

3. **Use structured logging:** Always use keyword arguments, never string formatting

   ```python
   logger.info("user_created", user_id="123", role="admin")  # ✅
   logger.info(f"User {user_id} created")  # ❌ NO
   ```

4. **Descriptive event names:** Use `snake_case` that answers "what happened?"
   - Good: `database_connection_established`, `tool_execution_started`, `api_request_completed`
   - Bad: `connected`, `done`, `success`

5. **Use logger.exception() in except blocks:** Captures full stack trace automatically

   ```python
   try:
       result = await operation()
   except ValueError:
       logger.exception("operation_failed", expected="int", received=type(value).__name__)
       raise
   ```

6. **Include debugging context:** IDs (user_id, request_id, session_id), input values, expected vs actual, external responses, performance metrics (duration_ms), `fix_suggestion` for AI self-correction

### Recommended (SHOULD)

- Log entry/exit for complex operations with relevant metadata
- Log performance metrics for bottlenecks (timing, counts)
- Log state transitions (old_state, new_state)
- Log external system interactions (API calls, database queries, tool executions)
- Use `bind_context()` for request-scoped data (middleware handles this automatically)

### DO NOT

- **DO NOT log sensitive data:** No passwords, API keys, tokens (mask: `api_key[:8] + "..."`)
- **DO NOT use string formatting:** Always use structured kwargs
- **DO NOT spam logs in loops:** Log batch summaries instead
- **DO NOT silently catch exceptions:** Always log with `logger.exception()` or re-raise
- **DO NOT use vague event names:** Be specific about what happened

### Common Patterns

**Tool execution:**

```python
logger.info("tool_execution_started", tool=name, params=params)
try:
    result = await tool.execute(params)
    logger.info("tool_execution_completed", tool=name, duration_ms=duration)
except ToolError:
    logger.exception("tool_execution_failed", tool=name, retry_count=count,
                     fix_suggestion="Check tool parameters or retry with different values")
    raise
```

**External API calls:**

```python
logger.info("api_call", provider="openai", endpoint="/v1/chat", status=200,
            duration_ms=1245.5, tokens={"prompt": 245, "completion": 128})
```

### Debugging

Logs include: `correlation_id` (links request logs), `source` (file:function:line), `duration_ms` (performance), `exc_type/exc_message` (errors), `fix_suggestion` (AI-readable guidance). Use `grep "correlation_id=abc-123"` to trace requests.

---

## Development Workflow

**Run server:** `uv run uvicorn src.main:app --host 0.0.0.0 --port 8030 --reload`

**Lint/check (must pass):** `uv run ruff check src/ && uv run mypy src/`

**Auto-fix:** `uv run ruff check --fix src/`

**Run tests:** `uv run pytest tests/ -v`

---

## Testing

**Tests mirror the source directory structure.** Every file in `src/` MUST have a corresponding test file.

**Structure:**

```
src/shared/logging.py  →  tests/shared/test_logging.py
src/shared/config.py   →  tests/shared/test_config.py
src/agent/agent.py     →  tests/agent/test_agent.py
```

**Requirements:**

- **Unit tests:** Test individual components in isolation. Mark with `@pytest.mark.unit`
- **Integration tests:** Test multiple components together. Mark with `@pytest.mark.integration`
- Place integration tests in `tests/integration/` when testing full application stack

**Run tests:** `uv run pytest tests/ -v`

**Run specific types:** `uv run pytest tests/ -m unit` or `uv run pytest tests/ -m integration`
