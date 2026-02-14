# SKILL.md — LLM Development Instructions for mochi-server

> This file contains instructions, context, and constraints that any LLM (coding assistant, agent, copilot) **must** follow when developing the `mochi-server` application. Read this file in full before writing any code.

---

## 1. Project Identity

- **Package name (PyPI):** `mochi-server`
- **Import name:** `mochi_server`
- **What it is:** A headless FastAPI server that wraps Ollama and provides REST + SSE APIs for LLM conversations, session persistence, tool execution, and agent orchestration.
- **What it is NOT:** A UI application. mochi-server contains zero rendering, terminal, or frontend code.
- **Specification:** The specification document `mochi_server_specs.md` is the single source of truth for all behavior.

---

## 2. Mandatory Reading Before You Code

Before writing or modifying **any** code in this project you must read and understand:

1. **`mochi_server_specs.md`** — The full specification. Every endpoint, every data model, every flow is defined there.
2. **This file (`SKILL.md`)** — Development rules and constraints.
3. **`pyproject.toml`** — Dependencies and build configuration.
4. **The module you are about to touch** — Always read the existing file before editing.

Do not guess behavior. If the spec does not cover something, ask the user before inventing behavior.

---

## 3. Technology Stack & Tooling

| Concern | Choice | Notes |
|---|---|---|
| Language | Python ≥ 3.11 | Use modern syntax: `X | None` over `Optional[X]`, `list[str]` over `List[str]` |
| Framework | FastAPI | Use dependency injection, Pydantic models for request/response, async route handlers |
| ASGI Server | uvicorn | Default entry point |
| Dependency Management | **`uv`** | All dependency operations use `uv add`, `uv remove`, `uv run`, `uv sync`. Never use `pip install` directly. |
| Build Backend | hatchling | Configured in `pyproject.toml` |
| Ollama Client | `ollama` (Python SDK) | **Async only** — use `ollama.AsyncClient` with `stream=True` for all chat interactions |
| Structured Output | `ollama-instructor` | For Pydantic-validated LLM responses (summarization) |
| Validation | Pydantic v2 | All API request/response models |
| Configuration | pydantic-settings | `MochiServerSettings` with `MOCHI_` env prefix |
| Streaming | `sse-starlette` | Server-Sent Events for chat streaming |
| Testing | pytest + pytest-asyncio + httpx | Use `httpx.AsyncClient` as the test client for FastAPI |
| Linting | ruff | Follow existing ruff configuration |
| Type Checking | mypy (optional) | `py.typed` marker is included |

---

## 4. Project Layout Rules

```
src/
└── mochi_server/
    ├── __init__.py              # create_app factory, version
    ├── __main__.py              # CLI: `mochi-server` command
    ├── py.typed
    ├── app.py                   # FastAPI app factory, lifespan
    ├── config.py                # MochiServerSettings
    ├── dependencies.py          # FastAPI Depends() providers
    ├── models/                  # Pydantic request/response schemas
    ├── routers/                 # FastAPI route handlers
    ├── ollama/                  # Ollama client wrappers
    ├── sessions/                # ChatSession, message types, CRUD
    ├── tools/                   # Tool discovery, schema, execution
    ├── agents/                  # Agent discovery, execution, tool factory
    ├── services/                # Context window, summarization, system prompts
    └── constants.py
```

### Rules:

- **One concern per module.** Do not mix router logic with business logic.
- **Routers only handle HTTP.** They validate input, call services, return responses. No business logic in routers.
- **Services contain business logic.** They do not import FastAPI or know about HTTP.
- **Models are pure Pydantic schemas.** They do not contain logic beyond validation.
- **Every `__init__.py` must export public symbols** so that `from mochi_server.sessions import SessionManager` works cleanly.
- **No circular imports.** Use `TYPE_CHECKING` guards when needed, but prefer restructuring over workarounds.

---

## 5. Coding Standards

### 5.1 Style

- Use **4-space indentation** (no tabs).
- Maximum line length: **120 characters** (not 79 — this is a modern codebase).
- Use **double quotes** for strings.
- Use **trailing commas** in multi-line data structures and function signatures.
- Always add **type hints** to function parameters and return types.
- Write **docstrings** for every public class and function (Google style).

### 5.2 Naming

| Thing | Convention | Example |
|---|---|---|
| Modules | `snake_case` | `context_window.py` |
| Classes | `PascalCase` | `SessionManager` |
| Functions / Methods | `snake_case` | `list_sessions()` |
| Constants | `UPPER_SNAKE_CASE` | `SUMMARY_UNSUPPORTED_MODELS` |
| Pydantic models | `PascalCase` with descriptive suffix | `ChatRequest`, `SessionListResponse` |
| Router tags | Plural noun | `"sessions"`, `"tools"`, `"agents"` |

### 5.3 Imports

- Group imports: stdlib → third-party → local.
- Use absolute imports within the package: `from mochi_server.sessions.session import ChatSession`.
- Never use wildcard imports (`from x import *`).

### 5.4 Error Handling

- Use **custom exception classes** that map to HTTP status codes.
- Catch specific exceptions, never bare `except:`.
- Every error response must follow the spec's error format: `{"error": {"code": "...", "message": "...", "details": {}}}`.
- Use FastAPI exception handlers to convert domain exceptions to HTTP responses.

### 5.5 Async vs Sync

- **Route handlers** must be `async def`.
- **Ollama communication** uses `ollama.AsyncClient` exclusively. There is no sync client. All chat interactions use `stream=True` and are consumed as async iterators. The non-streaming HTTP endpoint (`POST /chat/{session_id}`) internally calls `chat_stream()` and collects the full response before returning.
- **File I/O** (session load/save) can be synchronous — the files are small and local.
- **Background tasks** (summarization) use FastAPI's `BackgroundTasks`.
- **Expensive objects** (`OllamaClient`, discovery services) are created once at startup via FastAPI's lifespan context and reused for every request. Lightweight objects (`SessionManager`) can be created per-request.

---

## 6. API Design Rules

### 6.1 Versioning

All endpoints are under `/api/v1/`. This is non-negotiable for the first version.

### 6.2 REST Conventions

- Use **plural nouns** for resources: `/sessions`, `/tools`, `/agents`.
- Use **HTTP methods** correctly: GET (read), POST (create/action), PUT (full update), PATCH (partial update), DELETE (remove).
- Return **201** for resource creation, **200** for success, **204** for deletion.
- Return proper **4xx/5xx** error codes with the error response body.

### 6.3 Pydantic Models

- Every request body has a dedicated Pydantic model (e.g., `ChatRequest`, `CreateSessionRequest`).
- Every response body has a dedicated Pydantic model (e.g., `SessionResponse`, `ToolListResponse`).
- Use `model_config = ConfigDict(from_attributes=True)` when converting from dataclasses/ORM objects.
- Mark optional fields explicitly with `X | None = None`.

### 6.4 SSE Streaming

- Use `sse-starlette`'s `EventSourceResponse`.
- Every SSE event must have an `event` type and JSON `data`.
- The event types are defined in the spec (Appendix A). Do not invent new event types without updating the spec.
- Always send a final `done` event to signal stream completion.
- Handle client disconnection gracefully (save partial response).

---

## 7. Session Format Compatibility

**Critical:** mochi-server MUST read and write session JSON files in the defined format (format version `1.3`). This includes:

- The `metadata` object structure with all fields (session_id, model, created_at, updated_at, message_count, summary, summary_model, format_version, tool_settings, agent_settings, context_window_config).
- The `messages` array with role-specific fields (UserMessage, SystemMessage, SessionMessage with tool_calls, ToolMessage with tool_name).
- The `dataclasses.asdict()` serialization approach for messages.
- The format version migration logic (1.0 → 1.1 → 1.2 → 1.3).

If you change the session format, you **must** increment the format version and add migration logic.

---

## 8. Tool System Rules

- Tools are discovered from a user-provided directory at runtime. The server does not bundle any tools.
- Tool discovery loads `__init__.py`, reads `__all__`, validates functions (callable + has docstring).
- Tool groups are extracted from `__dunder__` variables in `__init__.py`.
- Schema conversion uses `ollama._utils.convert_function_to_tool`. Do not reimplement this.
- Tool execution must respect the configured `ToolExecutionPolicy`.
- For `always_confirm` policy: the server emits a `tool_call_confirmation_required` SSE event and waits for a client HTTP callback (`POST /api/v1/chat/{session_id}/confirm-tool`).
- Tool results are always strings (for LLM consumption).

---

## 9. Agent System Rules

- Agents are discovered from a user-provided directory. The server does not bundle any agents.
- The `agent` tool has a **dynamically generated docstring** listing enabled agents. A new function object must be created each time the enabled list changes (for cache invalidation keyed on `id(func)`).
- The two-phase planning + execution loop is the core of agent execution. Do not simplify or skip phases.
- Ephemeral prompts (planning/execution) are loaded from configurable file paths. They are appended to the API request but **never** persisted to the agent chat history.
- Agent chat sessions use the same `ChatSession` class and JSON format as user sessions.
- System prompts are **refreshed from SKILL.md** on every agent invocation.

---

## 10. Configuration Rules

- All paths (sessions_dir, tools_dir, agents_dir, system_prompts_dir) are resolved relative to `data_dir`.
- Never hardcode paths. Always read from `MochiServerSettings`.
- Use the `MOCHI_` environment variable prefix for all settings.
- Provide sensible defaults that work for local development (e.g., `data_dir="."`, `ollama_host="http://localhost:11434"`).

---

## 11. Testing Rules

- Every new feature must have unit tests.
- Every new API endpoint must have integration tests using `httpx.AsyncClient`.
- Use `tmp_path` for all file I/O in tests. Never write to the real filesystem.
- Mock the Ollama client in unit/integration tests. Do not require a running Ollama instance.
- Mark tests that require a real Ollama instance with `@pytest.mark.e2e`.
- Test both success and error paths.
- Use factories or fixtures for creating test sessions, messages, and tool functions.
- run `ruff check` to check code style and formatting.

---

## 12. Dependency Rules

- **Add dependencies with `uv add`**, not pip.
- **Dev dependencies go in `[dependency-groups] dev`**, added with `uv add --group dev`.
- Do not add dependencies that duplicate existing functionality. For example:
  - Do not add a separate JSON schema library — use Pydantic.
  - Do not add a separate HTTP client — use the `ollama` SDK's built-in client.
  - Do not add a task queue — use FastAPI's `BackgroundTasks`.
- Pin minimum versions in `pyproject.toml` using `>=` (e.g., `fastapi>=0.115.0`), not exact pins.

---

## 13. Common Pitfalls to Avoid

1. **Do not put UI logic in mochi-server.** No Rich, no prompt_toolkit. No print statements for user-facing output — use `logging`.

2. **Do not hardcode `Path.cwd()`.** All paths must come from configuration.

3. **Do not use global mutable state.** Caching should be scoped to service instances managed by FastAPI's dependency injection or lifespan.

4. **Do not block the async event loop.** All Ollama calls use the async client. File I/O is fine synchronous (fast, local).

5. **Do not break session format compatibility.** Maintain the defined JSON session format. If you change it, increment the format version and add migration logic.

6. **Do not add authentication in v1.** Auth is out of scope for the initial version. Design routes so auth can be added as middleware later.

7. **Do not swallow exceptions.** Log them with proper context, then raise appropriate HTTP errors.

8. **Do not skip the planning phase** in agent execution. Even if it seems unnecessary, the two-phase loop is part of the spec.

---

## 14. Development Workflow

### Starting the server locally:

```bash
uv run mochi-server
# or with options:
uv run mochi-server --host 0.0.0.0 --port 9000 --ollama-host http://localhost:11434
```

### Running tests:

```bash
uv run pytest
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest -m e2e  # requires running Ollama
```

### Linting:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### Adding a new dependency:

```bash
uv add some-package
uv add --group dev some-dev-package
```

---

## 15. Evolution Plan

mochi-server is built incrementally through a series of **evolution phases**, each producing a working, testable application. The full plan is defined in **`mochi_server_evolution_steps.md`** — that document is the authoritative guide for implementation order and scope.

### Summary of Phases

| Phase | Name | What You Get |
|-------|------|-------------|
| 0 | Foundation | Running FastAPI server with a static health endpoint |
| 1 | Ollama Integration | Server connects to Ollama, lists models, reports real connectivity |
| 2 | Sessions & Persistence | Create, list, retrieve, and delete sessions stored as JSON files |
| 3 | Non-Streaming Chat | Send a message and receive a complete response |
| 4 | Streaming Chat | Real-time SSE streaming, message editing, and re-generation |
| 5 | System Prompts | Manage prompt files and apply them to sessions |
| 6 | Context Window Management | Dynamic context window sizing and session status |
| 7 | Tool System | Discover, execute, and confirm tools during chat |
| 8 | Agent System | Two-phase agent orchestration with dedicated sessions |
| 9 | Summarization | Background conversation summaries after each response |

### Rules

- **Follow the phases in order.** Each phase builds on the previous one.
- **Use branches** to isolate and ensure each phase is complete before moving on.
- **Complete all tests** for a phase before moving to the next.
- **Review & refactor** after each phase — update `mochi_server_specs.md` if the implementation revealed spec issues.
- **Never skip ahead.** If a later phase depends on earlier work, that earlier work must be solid first.
- When starting a new phase, read its section in `mochi_server_evolution_steps.md` in full before writing code.
- **Ask the user** when a new requirement from the user violates the spec.

---

## 16. When You Are Unsure

- **Check the spec first** (`mochi_server_specs.md`).
- **Ask the user** if the spec is ambiguous or contradictory.
- **Never invent API behavior** that is not in the spec. If you think something is missing, flag it.

---
