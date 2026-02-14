# Mochi Server — Evolution Plan

> Each phase produces a **working, testable application**. No phase leaves the codebase in a broken state.
> After completing a phase, review what was learned and update `mochi_server_specs.md` if needed.

---

## How to Use This Document

1. **Start at Phase 0** and work through each phase sequentially.
2. **Complete all tests** for a phase before moving to the next.
3. **Review & Refactor** at the end of each phase — update specs, clean up code, adjust plans.
4. Each phase section lists exactly what is **new**, what **changes**, and how to **verify** success.
5. The spec (`mochi_server_specs.md`) remains the source of truth for detailed behavior. This document defines the *order* and *scope* of implementation.

---

## Phase Overview

| Phase | Name | What You Get |
|-------|------|-------------|
| 0 | [Foundation](#phase-0-foundation) | A running FastAPI server with a static health endpoint |
| 1 | [Ollama Integration](#phase-1-ollama-integration) | Server connects to Ollama, lists models, reports real connectivity |
| 2 | [Sessions & Persistence](#phase-2-sessions--persistence) | Create, list, retrieve, and delete sessions stored as JSON files |
| 3 | [Non-Streaming Chat](#phase-3-non-streaming-chat) | Send a message and receive a complete response |
| 4 | [Streaming Chat](#phase-4-streaming-chat) | Real-time SSE streaming, message editing, and re-generation |
| 5 | [System Prompts](#phase-5-system-prompts) | Manage prompt files and apply them to sessions |
| 6 | [Context Window Management](#phase-6-context-window-management) | Dynamic context window sizing and session status |
| 7 | [Tool System](#phase-7-tool-system) | Discover, execute, and confirm tools during chat |
| 8 | [Agent System](#phase-8-agent-system) | Two-phase agent orchestration with dedicated sessions |
| 9 | [Summarization](#phase-9-summarization) | Background conversation summaries after each response |

---

## Phase 0: Foundation

### Goal

A FastAPI application that starts via CLI, responds to a health check, and has the full project structure scaffolded. This is the skeleton that everything else will grow into.

### Builds On

Nothing — this is the starting point.

### New Dependencies

```
fastapi>=0.115.0
uvicorn>=0.34.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
```

Dev dependencies:

```
pytest>=8.0.0
pytest-asyncio>=0.25.0
httpx>=0.28.0
ruff>=0.11.0
```

### New Files

```
src/mochi_server/
├── __init__.py              # Package init: __version__, create_app()
├── __main__.py              # `python -m mochi_server` entry point
├── py.typed                 # PEP 561 marker (already exists)
├── app.py                   # FastAPI app factory, lifespan, router inclusion
├── config.py                # MochiServerSettings (pydantic-settings)
├── dependencies.py          # get_settings() dependency provider
├── constants.py             # Shared constants (empty for now)
│
├── models/
│   └── __init__.py
│   └── health.py            # HealthResponse schema
│
├── routers/
│   ├── __init__.py
│   └── health.py            # GET /api/v1/health
│
├── ollama/
│   └── __init__.py          # (empty, placeholder)
├── sessions/
│   └── __init__.py          # (empty, placeholder)
├── tools/
│   └── __init__.py          # (empty, placeholder)
├── agents/
│   └── __init__.py          # (empty, placeholder)
└── services/
    └── __init__.py          # (empty, placeholder)

tests/
├── __init__.py
├── conftest.py              # test_app fixture with httpx.AsyncClient
└── unit/
    ├── __init__.py
    └── test_health.py       # Health endpoint tests
```

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Returns static health status |

Response (Phase 0 — no Ollama check yet):

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### Key Implementation Notes

- `app.py` contains a `create_app()` factory that creates the FastAPI instance, registers routers, and defines the lifespan.
- `__init__.py` re-exports `create_app` and `__version__`.
- `__main__.py` uses `uvicorn.run()` with CLI argument parsing (host, port, log-level).
- `config.py` defines `MochiServerSettings` with all settings from the spec, even though most aren't used yet. This avoids future refactoring.
- `dependencies.py` provides `get_settings()` via `lru_cache` for dependency injection.
- `pyproject.toml` gets updated with all dependencies and the `[project.scripts]` entry for `mochi-server`.
- All placeholder `__init__.py` files in subpackages are empty — they exist only to establish the directory structure.

### Testing

- Health endpoint returns 200 with correct JSON.
- App factory creates a valid FastAPI instance.
- Settings load correctly with defaults.
- Settings can be overridden via environment variables.

### Definition of Done

```bash
# Server starts
uv run mochi-server

# Health check works
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "version": "0.1.0"}

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Does the project structure feel right?
- Are imports clean and the package installable?
- Update the spec if any config defaults changed.

---

## Phase 1: Ollama Integration

### Goal

The server can connect to a running Ollama instance, verify connectivity, and list available models with detailed information. The health endpoint now reports real Ollama connection status.

### Builds On

Phase 0 (Foundation).

### New Dependencies

```
ollama>=0.5.0
```

### New Files

```
src/mochi_server/
├── ollama/
│   ├── __init__.py          # Export OllamaClient
│   ├── client.py            # Sync OllamaClient wrapper
│   └── types.py             # ModelInfo dataclass
│
├── models/
│   └── models.py            # ModelListResponse, ModelDetailResponse schemas
│
├── routers/
│   └── models.py            # GET /api/v1/models, GET /api/v1/models/{name}

tests/
├── unit/
│   ├── test_ollama_client.py
│   └── test_models_api.py
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_ollama_client()` provider |
| `app.py` | Register models router |
| `models/health.py` | Add `ollama_connected`, `ollama_host` fields |
| `routers/health.py` | Check Ollama connectivity, return real status |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/models` | List all available Ollama models |
| `GET` | `/api/v1/models/{model_name}` | Get details for a specific model |

### Key Implementation Notes

- `OllamaClient` wraps `ollama.Client` and provides: `list_models()`, `get_model_info(name)`, `check_connection()`.
- `ModelInfo` is a dataclass holding model metadata (name, size, format, family, parameter_size, quantization, capabilities, context_length).
- Model capabilities are derived from the model's metadata (e.g., "tools" support).
- The health endpoint catches connection errors gracefully — if Ollama is down, it returns `"status": "ok", "ollama_connected": false` (the server itself is healthy).
- Model filtering: Exclude models that are embeddings-only (no completion capability).

### Testing

- Mock `ollama.Client` in all tests — no real Ollama required.
- Test model listing returns expected format.
- Test model detail for a specific model.
- Test model not found returns 404.
- Test health endpoint when Ollama is connected.
- Test health endpoint when Ollama is unreachable.

### Definition of Done

```bash
# Health shows Ollama status
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "ollama_connected": true, "ollama_host": "http://localhost:11434", "version": "0.1.0"}

# Models list works
curl http://localhost:8000/api/v1/models
# → {"models": [{"name": "qwen3:14b", "size_mb": 9048.2, ...}]}

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the Ollama client abstraction at the right level?
- Does `ModelInfo` capture everything we need?
- Are connection errors handled cleanly?

---

## Phase 2: Sessions & Persistence

### Goal

Full session lifecycle management: create sessions, list them, retrieve details with message history, delete them, and update basic metadata. Sessions are persisted as JSON files that follow the spec's format (version `1.3`).

### Builds On

Phase 1 (Ollama Integration) — session creation validates that the model exists.

### New Files

```
src/mochi_server/
├── sessions/
│   ├── __init__.py          # Export SessionManager, ChatSession, message types
│   ├── session.py           # ChatSession class, load/save JSON
│   ├── manager.py           # SessionManager: CRUD operations
│   ├── types.py             # Message dataclasses, SessionMetadata, SessionCreationOptions
│   └── migration.py         # Format version migration (1.0 → 1.3)
│
├── models/
│   └── sessions.py          # CreateSessionRequest, SessionResponse, SessionListResponse, etc.
│
├── routers/
│   └── sessions.py          # /api/v1/sessions/* endpoints

tests/
├── unit/
│   ├── test_session.py          # ChatSession load/save
│   ├── test_session_manager.py  # CRUD operations
│   └── test_session_migration.py
├── integration/
│   ├── __init__.py
│   └── test_session_api.py      # Full endpoint tests
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_session_manager()` provider |
| `app.py` | Register sessions router |
| `config.py` | Verify `sessions_dir` resolution logic works correctly |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sessions` | Create a new session |
| `GET` | `/api/v1/sessions` | List all sessions (sorted by `updated_at` desc) |
| `GET` | `/api/v1/sessions/{session_id}` | Get session details + message history |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete a session |
| `PATCH` | `/api/v1/sessions/{session_id}` | Update session metadata (model only in this phase) |
| `GET` | `/api/v1/sessions/{session_id}/messages` | Get messages for a session |

### Key Implementation Notes

- Session IDs are 10-character random alphanumeric strings.
- `ChatSession` handles loading/saving JSON, adding messages, and managing metadata.
- `SessionManager` provides the CRUD layer on top of `ChatSession`, operating on a `sessions_dir`.
- The JSON format exactly matches the spec's schema (format version `1.3`).
- Message types are Python dataclasses: `UserMessage`, `SystemMessage`, `AssistantMessage`, `ToolMessage`.
- Messages are serialized via `dataclasses.asdict()`.
- Format migration handles 1.0 → 1.1 → 1.2 → 1.3 for reading older session files.
- `POST /sessions` requires a `model` field. The router validates the model exists by calling the Ollama client.
- `tool_settings` and `agent_settings` are accepted in `POST /sessions` and stored in metadata, but not acted upon yet (those features come in later phases).
- Session listing returns summaries and previews (preview = first user message content, truncated).

### Testing

- `ChatSession`: create, add messages, save to disk, load from disk, verify round-trip fidelity.
- `SessionManager`: create, list (sorted correctly), get, delete, not-found errors.
- Format migration: test loading files in format 1.0, 1.1, 1.2 and verify they're migrated to 1.3.
- API integration: test all endpoints with `httpx.AsyncClient`.
- All file I/O tests use `tmp_path`.

### Definition of Done

```bash
# Create a session
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:14b"}'
# → {"session_id": "a1b2c3d4e5", "model": "qwen3:14b", "created_at": "...", ...}

# List sessions
curl http://localhost:8000/api/v1/sessions
# → {"sessions": [...]}

# Get a session
curl http://localhost:8000/api/v1/sessions/a1b2c3d4e5
# → {session details + messages}

# Delete a session
curl -X DELETE http://localhost:8000/api/v1/sessions/a1b2c3d4e5
# → 204

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the session JSON format exactly right?
- Does the migration logic handle edge cases?
- Is `SessionManager` easy to test in isolation?
- Should we adjust the spec based on anything we learned about session storage?

---

## Phase 3: Non-Streaming Chat

### Goal

Send a message to a session and receive a complete (non-streaming) assistant response. The full round-trip works: user message saved → sent to Ollama → assistant response saved → returned to client.

### Builds On

Phase 2 (Sessions) — requires sessions to exist before chatting.

### New Files

```
src/mochi_server/
├── models/
│   └── chat.py              # ChatRequest, ChatResponse, MessageResponse schemas
│
├── routers/
│   └── chat.py              # POST /api/v1/chat/{session_id}

tests/
├── unit/
│   └── test_chat_service.py     # Chat logic tests
├── integration/
│   └── test_chat_api.py         # Chat endpoint tests
```

### Modified Files

| File | Changes |
|------|---------|
| `ollama/client.py` | Add `chat()` method (non-streaming, sync) |
| `dependencies.py` | Add any chat-specific dependencies if needed |
| `app.py` | Register chat router |
| `sessions/session.py` | Ensure `add_message()` handles all message types correctly |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat/{session_id}` | Send a message and get a complete response |

### Key Implementation Notes

- The chat endpoint flow:
  1. Load the session from disk.
  2. Add the user message to the session.
  3. Build the message history for Ollama (convert session messages to Ollama's format).
  4. Call `OllamaClient.chat()` with the message history and model.
  5. Create an `AssistantMessage` from Ollama's response.
  6. Add the assistant message to the session.
  7. Save the session to disk.
  8. Return the response.
- The `think` parameter in the request is passed to Ollama if the model supports it.
- If the session doesn't exist, return 404.
- If Ollama returns an error, propagate it with the spec's error format.
- The non-streaming endpoint uses Ollama's sync client with `stream=False`.
- No tool handling yet — tool calls in the response are ignored in this phase.
- No context window management yet — the full message history is sent.
- The response includes `tool_calls_executed: []` and a placeholder `context_window` object.

### Testing

- Chat with a mocked Ollama that returns a simple response.
- Verify user message is saved to the session.
- Verify assistant message is saved to the session.
- Verify message metadata (message_id, timestamp, eval_count, etc.).
- Test chat with nonexistent session → 404.
- Test chat when Ollama is unreachable → appropriate error.

### Definition of Done

```bash
# Create a session first
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:14b"}' | jq -r '.session_id')

# Send a message
curl -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the capital of France?"}'
# → {"session_id": "...", "message": {"role": "assistant", "content": "...", ...}}

# Verify messages are persisted
curl "http://localhost:8000/api/v1/sessions/$SESSION_ID/messages"
# → Shows both user and assistant messages

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the message format conversion to/from Ollama clean?
- Is the chat flow easy to extend with streaming, tools, and agents?
- Are error cases handled properly?

---

## Phase 4: Streaming Chat

### Goal

Real-time streaming responses via SSE, plus message editing and re-generation. This is the primary way clients will interact with the chat API.

### Builds On

Phase 3 (Non-Streaming Chat) — same flow but streamed.

### New Dependencies

```
sse-starlette>=2.0.0
```

### New Files

```
tests/
├── integration/
│   └── test_chat_stream_api.py  # SSE streaming tests
```

### Modified Files

| File | Changes |
|------|---------|
| `ollama/client.py` | Add `chat_stream()` method (sync, yields chunks) |
| `routers/chat.py` | Add `POST /api/v1/chat/{session_id}/stream` endpoint |
| `models/chat.py` | Add SSE event payload schemas |
| `sessions/session.py` | Add `edit_message()` and `truncate_after()` methods |
| `routers/sessions.py` | Add `PUT /sessions/{id}/messages/{index}` endpoint |
| `models/sessions.py` | Add `EditMessageRequest` schema |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat/{session_id}/stream` | Streaming SSE chat response |
| `PUT` | `/api/v1/sessions/{session_id}/messages/{message_index}` | Edit a message and truncate subsequent messages |

### SSE Events Implemented in This Phase

| Event | When |
|-------|------|
| `content_delta` | Each text chunk from Ollama |
| `thinking_delta` | Each thinking block chunk (when `think=true`) |
| `message_complete` | After all chunks received, with full message metadata |
| `error` | If an error occurs during streaming |
| `done` | Stream is complete |

### Key Implementation Notes

- Streaming uses `sse-starlette`'s `EventSourceResponse` wrapping an async generator.
- The sync `OllamaClient.chat_stream()` runs in a thread via `asyncio.to_thread()` to avoid blocking the event loop. The sync generator is consumed in the thread and chunks are put into an `asyncio.Queue` that the async generator reads from.
- Each SSE event is a JSON object with an `event` type field.
- The assistant message is accumulated during streaming, then saved to the session when the stream completes.
- If the client disconnects mid-stream, save whatever content was generated so far.
- Message editing (`PUT /sessions/{id}/messages/{index}`) edits the message content in place and removes all messages after it. The client can then call the stream endpoint again (without a `message` field) to re-generate from the last user message.
- The stream endpoint accepts an optional `message` field. If absent, it re-generates a response from the existing message history (used after editing).

### Testing

- Verify SSE events arrive in the correct order: `content_delta`+ → `message_complete` → `done`.
- Verify thinking deltas are sent when `think=true`.
- Verify accumulated message is saved to session.
- Test message editing truncates correctly.
- Test re-generation after edit.
- Test error event on Ollama failure.

### Definition of Done

```bash
# Stream a response
curl -N -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a story"}'
# → SSE events streamed in real time

# Edit a message
curl -X PUT "http://localhost:8000/api/v1/sessions/$SESSION_ID/messages/0" \
  -H "Content-Type: application/json" \
  -d '{"content": "Tell me a joke instead"}'
# → 200

# Re-generate
curl -N -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/stream" \
  -H "Content-Type: application/json" \
  -d '{}'
# → New streamed response

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the async generator pattern clean and maintainable?
- Does the thread-based streaming hold up under concurrent requests?
- Is SSE event serialization consistent?
- Revisit the chat router — is it getting too large? Consider extracting a chat service.

---

## Phase 5: System Prompts

### Goal

Manage system prompt files on disk and apply them to sessions. System prompts are set when creating a session or updated on an existing session.

### Builds On

Phase 4 (Streaming Chat) — system prompts affect how chat messages are sent to Ollama.

### New Files

```
src/mochi_server/
├── services/
│   └── system_prompts.py    # SystemPromptService
│
├── models/
│   └── system_prompts.py    # SystemPromptListResponse, SystemPromptResponse schemas
│
├── routers/
│   └── system_prompts.py    # /api/v1/system-prompts/* endpoints

tests/
├── unit/
│   └── test_system_prompts.py
├── integration/
│   └── test_system_prompts_api.py
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_system_prompt_service()` provider |
| `app.py` | Register system-prompts router |
| `routers/sessions.py` | Add system prompt endpoints on sessions; handle `system_prompt` in `POST /sessions` |
| `routers/chat.py` | Include system prompt as the first message in Ollama requests |
| `sessions/session.py` | Add/update/remove system message in message history |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/system-prompts` | List all system prompt files |
| `GET` | `/api/v1/system-prompts/{filename}` | Get content of a prompt file |
| `POST` | `/api/v1/system-prompts` | Create a new prompt file |
| `PUT` | `/api/v1/system-prompts/{filename}` | Update a prompt file |
| `DELETE` | `/api/v1/system-prompts/{filename}` | Delete a prompt file |
| `PUT` | `/api/v1/sessions/{session_id}/system-prompt` | Set/update session system prompt |
| `DELETE` | `/api/v1/sessions/{session_id}/system-prompt` | Remove session system prompt |

### Key Implementation Notes

- `SystemPromptService` operates on the configured `system_prompts_dir`.
- Prompt files are markdown (`.md`) files.
- Listing returns filename, preview (first N characters), and word count.
- When a system prompt is set on a session, it becomes the first message (role `"system"`) in the session's message history.
- If the system prompt is changed, the existing system message is replaced in-place (index 0).
- If removed, the system message is deleted and subsequent messages shift.
- The `source_file` field on the system message tracks which file the prompt came from.
- Chat flow (both streaming and non-streaming) now correctly includes the system message when building the Ollama request.

### Testing

- CRUD operations on prompt files (create, read, update, delete).
- List prompts returns correct previews and word counts.
- Setting a system prompt on a session adds it as the first message.
- Updating a system prompt replaces the existing one.
- Removing a system prompt deletes the system message.
- Chat includes the system prompt in the Ollama request.
- File validation: reject non-`.md` files, handle missing directory.

### Definition of Done

```bash
# List prompts
curl http://localhost:8000/api/v1/system-prompts
# → {"prompts": [...]}

# Set a system prompt on a session
curl -X PUT "http://localhost:8000/api/v1/sessions/$SESSION_ID/system-prompt" \
  -H "Content-Type: application/json" \
  -d '{"content": "You are a helpful coding assistant.", "source_file": "coder.md"}'
# → 200

# Chat now uses the system prompt
curl -N -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
# → Response influenced by system prompt

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is system prompt handling clean in the chat flow?
- Does the session correctly persist system prompt changes?
- Should system prompts support formats beyond `.md`?

---

## Phase 6: Context Window Management

### Goal

Dynamic context window sizing that adjusts based on model limits and conversation length. A status endpoint provides full session state information.

### Builds On

Phase 5 (System Prompts) — context window calculation needs to account for system prompts.

### New Files

```
src/mochi_server/
├── services/
│   └── context_window.py    # DynamicContextWindowService
│
├── models/
│   └── status.py            # SessionStatusResponse, ContextWindowInfo schemas

tests/
├── unit/
│   └── test_context_window.py
├── integration/
│   └── test_status_api.py
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_context_window_service()` provider |
| `routers/sessions.py` | Add `GET /sessions/{id}/status` endpoint |
| `routers/chat.py` | Integrate context window calculation before Ollama calls |
| `ollama/client.py` | Accept `num_ctx` option in `chat()` and `chat_stream()` |
| `sessions/types.py` | Add `ContextWindowConfig` to session metadata |
| `sessions/session.py` | Persist `context_window_config` in metadata |
| `models/chat.py` | Include `context_window` info in chat responses and `message_complete` events |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/sessions/{session_id}/status` | Full session status with context window info |

### Key Implementation Notes

- `DynamicContextWindowService` calculates the optimal context window size based on:
  - Model's maximum context length (from Ollama model info).
  - Current token usage (estimated from message history).
  - Configurable thresholds for scaling up/down.
- Context window config is stored in session metadata and persisted across requests.
- The chat flow now: (1) calculates context window, (2) passes `num_ctx` to Ollama, (3) includes context info in the response.
- The status endpoint aggregates session state: model, message count, context window info, active tools (empty for now), agents (empty for now), system prompt, and summary (null for now).
- `dynamic_context_window_enabled` setting controls whether dynamic sizing is active. When disabled, no `num_ctx` is passed (Ollama uses its default).

### Testing

- Context window calculation with various message history sizes.
- Context window respects model maximum.
- Context window config is persisted in session JSON.
- Status endpoint returns all expected fields.
- Chat response includes context window info.
- Test with dynamic context disabled.

### Definition of Done

```bash
# Check session status
curl "http://localhost:8000/api/v1/sessions/$SESSION_ID/status"
# → {"session_id": "...", "context_window": {"dynamic_enabled": true, "current_window": 8192, ...}, ...}

# Chat response includes context info
curl -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
# → {..., "context_window": {"current_window": 8192, "usage_tokens": 42, "reason": "initial_setup"}}

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the context window calculation accurate enough?
- Does the status endpoint return everything a client needs?
- Should we adjust context window defaults based on real-world testing?

---

## Phase 7: Tool System

### Goal

Discover tools from a directory, expose them via API, execute them during chat (both auto-execute and confirmation flow), and continue the conversation with tool results.

### Builds On

Phase 6 (Context Window) — tool schemas affect context, and tool settings are part of session status.

### New Files

```
src/mochi_server/
├── tools/
│   ├── __init__.py          # Export services
│   ├── config.py            # ToolExecutionPolicy, ToolSettings
│   ├── discovery.py         # ToolDiscoveryService
│   ├── schema.py            # ToolSchemaService
│   └── execution.py         # ToolExecutionService, ToolExecutionResult
│
├── models/
│   └── tools.py             # ToolListResponse, ToolConfirmationRequest schemas
│
├── routers/
│   └── tools.py             # /api/v1/tools/* endpoints

tests/
├── fixtures/
│   └── sample_tools/        # Test tool modules for discovery tests
│       ├── __init__.py
│       └── math_tools.py
├── unit/
│   ├── test_tool_discovery.py
│   ├── test_tool_schema.py
│   └── test_tool_execution.py
├── integration/
│   ├── test_tool_api.py
│   └── test_chat_with_tools.py
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_tool_discovery_service()`, `get_tool_schema_service()`, `get_tool_execution_service()` |
| `app.py` | Register tools router |
| `routers/chat.py` | Handle tool calls in streaming: detect tool_calls → execute → continue. Add `POST /chat/{id}/confirm-tool`. |
| `models/chat.py` | Add tool-related SSE event schemas |
| `routers/sessions.py` | `PATCH /sessions/{id}` now supports updating `tool_settings` |
| `sessions/types.py` | Ensure `ToolSettings` is fully defined |
| `routers/sessions.py` (status) | Status endpoint now includes `tools_enabled`, `active_tools`, `execution_policy` |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/tools` | List all discovered tools and tool groups |
| `GET` | `/api/v1/tools/{tool_name}` | Get details for a specific tool |
| `POST` | `/api/v1/tools/reload` | Force reload tools from disk |
| `POST` | `/api/v1/chat/{session_id}/confirm-tool` | Approve or deny a pending tool call |

### SSE Events Added in This Phase

| Event | When |
|-------|------|
| `tool_call` | LLM requested a tool (auto-execute policy) |
| `tool_call_confirmation_required` | LLM requested a tool (always_confirm policy) |
| `tool_result` | After tool execution completes |
| `tool_continuation_start` | Before sending tool results back to LLM for continuation |

### Key Implementation Notes

- **Tool Discovery:** `ToolDiscoveryService` scans the configured `tools_dir`, loads each subdirectory's `__init__.py`, reads `__all__`, and validates each exported symbol (must be callable with a docstring).
- **Tool Groups:** Extracted from `__dunder__` variables (e.g., `__group__ = "math"`) in each tool module's `__init__.py`.
- **Tool Schemas:** `ToolSchemaService` uses `ollama._utils.convert_function_to_tool` to convert Python functions into Ollama-compatible tool schemas. Do not reimplement this.
- **Tool Execution:** `ToolExecutionService` calls the tool function, catches exceptions, and returns a `ToolExecutionResult` with success/failure, result string, and error message.
- **Chat flow with tools (auto-execute / `never_confirm`):**
  1. Ollama returns a response containing `tool_calls`.
  2. Emit `tool_call` SSE event for each call.
  3. Execute each tool immediately.
  4. Emit `tool_result` SSE event for each result.
  5. Add the tool call and result messages to the session.
  6. Emit `tool_continuation_start` event.
  7. Send updated history (including tool results) back to Ollama.
  8. Stream the continuation response.
  9. Repeat if the continuation also contains tool calls.
- **Chat flow with tools (`always_confirm`):**
  1. Ollama returns `tool_calls`.
  2. Emit `tool_call_confirmation_required` SSE event with a `confirmation_id`.
  3. The stream pauses and waits for a client callback to `POST /chat/{id}/confirm-tool`.
  4. If approved, execute the tool and continue as above.
  5. If denied (or timeout), skip the tool and inform the LLM.
- **Confirmation state:** Pending confirmations are held in memory (e.g., an `asyncio.Event` + dict keyed by `confirmation_id`). They expire after a configurable timeout.
- Tool results are always converted to strings before being sent to the LLM.
- Session's `tool_settings` (set during creation or via `PATCH`) determines which tools are active and the execution policy.

### Testing

- **Discovery:** Test with sample tool modules in `tests/fixtures/sample_tools/`. Verify tools are found, invalid tools are skipped, groups are extracted.
- **Schema:** Verify schema conversion produces correct Ollama tool format.
- **Execution:** Test successful execution, exception handling, result formatting.
- **Chat with tools (auto-execute):** Mock Ollama to return tool_calls in its response. Verify the full loop: tool_call event → execution → tool_result event → continuation → final response.
- **Chat with tools (confirmation):** Verify confirmation_required event is emitted, confirm-tool endpoint works, denial skips execution, timeout is handled.
- **Tool API:** List tools, get tool details, reload tools.
- **Session status:** Verify tool info appears in status endpoint.

### Definition of Done

```bash
# List discovered tools
curl http://localhost:8000/api/v1/tools
# → {"tools": {"add_numbers": {...}}, "groups": {"math": [...]}}

# Chat with tools (auto-execute)
curl -N -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2 + 3?"}'
# → SSE: tool_call → tool_result → tool_continuation_start → content_delta... → done

# Confirm a tool call
curl -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/confirm-tool" \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id": "conf_abc123", "approved": true}'
# → 200

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the tool execution loop clean and easy to follow?
- Does the confirmation flow feel robust? Are race conditions handled?
- Is the chat router getting too complex? This is a good time to extract a dedicated `ChatService` if not done already.
- Are tool schemas cached appropriately?
- Update the spec if any tool behavior needed adjustment.

---

## Phase 8: Agent System

### Goal

Full agent orchestration: discover agents from a directory, expose them via API, execute them during chat using the two-phase (planning + execution) loop with dedicated agent chat sessions.

### Builds On

Phase 7 (Tool System) — agents use tools internally and are themselves invoked as a special tool in the main chat.

### New Dependencies

None — all required packages are already installed.

### New Files

```
src/mochi_server/
├── agents/
│   ├── __init__.py          # Export services
│   ├── config.py            # AgentSettings
│   ├── discovery.py         # AgentDiscoveryService, AgentDefinition
│   ├── execution.py         # AgentExecutionService (two-phase loop)
│   ├── tool_factory.py      # Dynamic agent tool builder
│   └── prompt_loader.py     # Ephemeral planning/execution prompt loading
│
├── models/
│   └── agents.py            # AgentListResponse, AgentDetailResponse, AgentChatResponse schemas
│
├── routers/
│   └── agents.py            # /api/v1/agents/* endpoints

tests/
├── fixtures/
│   └── sample_agents/       # Test agent directories
│       └── coder/
│           ├── SKILL.md
│           └── tools/
│               └── __init__.py
├── unit/
│   ├── test_agent_discovery.py
│   ├── test_agent_execution.py
│   └── test_agent_tool_factory.py
├── integration/
│   └── test_agent_api.py
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_agent_discovery_service()`, `get_agent_execution_service()` |
| `app.py` | Register agents router |
| `routers/chat.py` | Detect agent tool calls in the streaming loop and delegate to `AgentExecutionService` |
| `models/chat.py` | Add agent-related SSE event schemas |
| `routers/sessions.py` | `PATCH /sessions/{id}` now supports updating `agent_settings` |
| `sessions/types.py` | Ensure `AgentSettings` is fully defined |
| `routers/sessions.py` (status) | Status endpoint now includes `agents_enabled`, `enabled_agents` |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/agents` | List all discovered agents |
| `GET` | `/api/v1/agents/{agent_name}` | Get details for a specific agent |
| `POST` | `/api/v1/agents/reload` | Force reload agents from disk |
| `GET` | `/api/v1/agents/chats` | List all agent chat sessions |
| `GET` | `/api/v1/agents/chats/{session_id}` | Get an agent chat session |

### SSE Events Added in This Phase

| Event | When |
|-------|------|
| `agent_start` | Agent invocation begins |
| `agent_planning` | Content chunks during planning phase |
| `agent_execution` | Content chunks during execution phase |
| `agent_tool_call` | Agent calls one of its own tools |
| `agent_tool_result` | Result of an agent's tool execution |
| `agent_complete` | Agent execution finished, output ready |

### Key Implementation Notes

- **Agent Discovery:** `AgentDiscoveryService` scans the configured `agents_dir`. Each subdirectory with a `SKILL.md` file is an agent. `SKILL.md` contains a frontmatter-style header with `description` and optional `model`. The agent's tools are in a `tools/` subdirectory following the same discovery rules as the main tool system.
- **Agent Validation:** An agent is `valid` only if it has a `SKILL.md` and at least one discoverable tool.
- **Agent Tool Factory:** `tool_factory.py` creates a dynamic `agent` function whose docstring lists all enabled agents and their descriptions. This function is added to the tool schemas sent to Ollama so the LLM can invoke agents. A **new function object** must be created each time the enabled agent list changes, because Ollama's schema cache is keyed on `id(func)`.
- **Two-Phase Execution Loop:**
  1. **Planning phase:** The agent receives the user's instruction. An ephemeral planning prompt (loaded from `planning_prompt_path`) is appended to the request but **not** persisted. Ollama is called **without** tools. The planning response is saved to the agent's chat session.
  2. **Execution phase:** An ephemeral execution prompt (loaded from `execution_prompt_path`) is appended. Ollama is called **with** the agent's tools. If the response contains tool calls, they are executed and the results are sent back to Ollama. This loops until the LLM responds with plain text (no tool calls). The final response is saved.
- **Agent Chat Sessions:** Each agent invocation uses a dedicated `ChatSession` stored in `agent_chats_dir`. The same session format (v1.3) is used. Agent sessions are reused across invocations to maintain agent memory.
- **System Prompt Refresh:** On every agent invocation, the agent's system prompt is re-read from its `SKILL.md` file to pick up any changes.
- **Integration with main chat:** When the main LLM calls the `agent` tool during streaming, the chat router delegates to `AgentExecutionService`. Agent SSE events are forwarded to the client in real time. The agent's final output becomes the tool result in the main conversation, and the main LLM continues with it.
- Agents use their own model (if specified in `SKILL.md`) or fall back to the session's model.

### Testing

- **Discovery:** Test with sample agent directories. Verify agents are found, invalid agents are flagged, tools are counted.
- **Tool Factory:** Verify dynamic function generation, docstring content, function identity changes when agent list changes.
- **Prompt Loader:** Verify planning and execution prompts are loaded correctly, missing files are handled.
- **Execution:** Mock Ollama for both planning and execution phases. Verify:
  - Planning phase sends no tools.
  - Execution phase sends agent's tools.
  - Tool calls in execution phase are executed and looped.
  - Final output is returned correctly.
  - Agent chat session is persisted.
  - Ephemeral prompts are not persisted.
- **Integration:** Full flow: user message → LLM calls agent → agent plans → agent executes with tools → output returned → main LLM continues.
- **API:** List agents, get agent details, list/get agent chat sessions.

### Definition of Done

```bash
# List agents
curl http://localhost:8000/api/v1/agents
# → {"agents": {"coder": {"name": "coder", "valid": true, "tool_count": 6, ...}}}

# Chat triggers an agent (LLM decides to use it)
curl -N -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a Python function to sort a list"}'
# → SSE: agent_start → agent_planning → agent_execution → agent_tool_call →
#   agent_tool_result → agent_complete → content_delta... → done

# List agent chat sessions
curl http://localhost:8000/api/v1/agents/chats
# → List of agent chat sessions

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the two-phase loop clear and maintainable?
- Are agent chat sessions properly isolated from main sessions?
- Is the dynamic tool factory approach robust?
- Does the agent execution handle errors gracefully (tool failures, Ollama errors)?
- Is the chat router still manageable, or should agent delegation be extracted further?
- Update the spec if agent behavior needed any adjustments.

---

## Phase 9: Summarization

### Goal

Automatic background conversation summarization after each assistant response. Summaries provide a short description and topic list for each session, making session listing and management more useful.

### Builds On

Phase 8 (Agent System) — this is the final feature phase. All prior features are in place.

### New Dependencies

```
ollama-instructor>=0.1.0
```

### New Files

```
src/mochi_server/
├── ollama/
│   └── async_client.py      # AsyncOllamaClient + AsyncInstructorOllamaClient
│
├── services/
│   ├── summarization.py     # SummarizationService
│   └── summary_model.py     # SummaryModelManager

tests/
├── unit/
│   ├── test_summarization.py
│   └── test_summary_model.py
├── integration/
│   └── test_summarization_api.py
```

### Modified Files

| File | Changes |
|------|---------|
| `dependencies.py` | Add `get_summarization_service()`, `get_async_instructor_client()` |
| `routers/chat.py` | After saving assistant response, trigger background summarization via `BackgroundTasks` |
| `routers/sessions.py` | Add `POST /sessions/{id}/summarize` and `GET /sessions/{id}/summary` endpoints |
| `models/sessions.py` | Add `SummaryResponse`, `SummarizeRequest` schemas |
| `sessions/types.py` | Ensure `ConversationSummary` model is defined (summary + topics) |
| `sessions/session.py` | Ensure summary is persisted in metadata |
| `routers/sessions.py` (status) | Status endpoint now includes `summary` and `summary_model` |
| `constants.py` | Add `SUMMARY_UNSUPPORTED_MODELS` list |

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sessions/{session_id}/summarize` | Trigger immediate summary generation |
| `GET` | `/api/v1/sessions/{session_id}/summary` | Get current session summary |

### Key Implementation Notes

- **`AsyncInstructorOllamaClient`** wraps `ollama_instructor.OllamaInstructorAsync` and provides structured output — Ollama returns a response that is validated against a Pydantic model (`ConversationSummary`).
- **`ConversationSummary`** has two fields: `summary` (str) and `topics` (list[str]).
- **`SummarizationService`** takes a session's message history and generates a summary using the instructor client.
- **`SummaryModelManager`** determines which model to use for summarization:
  1. If the session's chat model supports structured output, use it.
  2. If the session has a stored `summary_model`, use that.
  3. If specified explicitly in the request, use that.
  4. Otherwise, skip summarization.
- **Trigger conditions** (all must be met for automatic summarization):
  - Summarization is enabled in settings (`summarization_enabled`).
  - The session has at least 2 messages.
  - The last message is from the assistant.
  - The last assistant message has no `tool_calls` (it's a final response, not a tool-calling intermediate).
- **Background execution:** After the chat streaming endpoint saves the assistant response, it adds a `BackgroundTasks` task that calls `SummarizationService.maybe_update_summary()`. This runs after the HTTP response is sent, so the client doesn't wait for it.
- **Manual trigger:** `POST /sessions/{id}/summarize` allows the client to force a summary generation, optionally specifying a model.
- **Error resilience:** If summarization fails (model unavailable, structured output parsing error), it logs the error and moves on. It never crashes the chat flow.
- Models in `SUMMARY_UNSUPPORTED_MODELS` (e.g., certain models that don't support structured output) are excluded from automatic model selection.

### Testing

- **SummarizationService:** Mock the instructor client. Verify summary is generated from message history. Verify result is saved to session metadata.
- **SummaryModelManager:** Test model selection logic with various scenarios (chat model supports structured output, fallback model, no suitable model).
- **Trigger conditions:** Test each condition independently. Verify summarization is skipped when conditions aren't met.
- **Background execution:** Verify summarization is triggered after chat response. Verify it doesn't block the response.
- **Error handling:** Verify summarization failures are logged but don't propagate.
- **API:** Test manual summarize endpoint, test get summary endpoint.
- **Session listing:** Verify summaries and topics appear in session list responses.

### Definition of Done

```bash
# Chat a few messages to trigger automatic summarization
curl -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about Python async patterns"}'

# Wait a moment for background task, then check summary
curl "http://localhost:8000/api/v1/sessions/$SESSION_ID/summary"
# → {"summary": "Discussion about Python async patterns...", "topics": ["python", "asyncio"]}

# Force a summary with a specific model
curl -X POST "http://localhost:8000/api/v1/sessions/$SESSION_ID/summarize" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:14b"}'
# → {"summary": "...", "topics": [...], "model_used": "qwen3:14b"}

# Session listing includes summaries
curl http://localhost:8000/api/v1/sessions
# → {"sessions": [{"session_id": "...", "summary": {"summary": "...", "topics": [...]}, ...}]}

# Tests pass
uv run pytest tests/
```

### Review & Refactor

- Is the background task approach reliable?
- Is the model selection logic sound?
- Do summaries add real value to the session listing?
- Is this a good time for a full integration test pass across all features?
- Final spec review: does the implemented behavior match the spec in all areas?

---

## After All Phases: Final Review

Once all 10 phases are complete, do a final comprehensive review:

1. **Full integration test suite** — run all tests, including cross-feature scenarios (e.g., chat with tools + agents + summarization).
2. **Spec alignment audit** — walk through `mochi_server_specs.md` section by section and verify every described behavior is implemented.
3. **Error handling audit** — verify all error codes from the spec are implemented and returned correctly.
4. **Performance check** — test with larger sessions, multiple concurrent streams, many tools/agents.
5. **Documentation** — update `README.md` with usage examples, API overview, and configuration reference.
6. **Spec update** — incorporate any learnings, corrections, or additions discovered during implementation back into `mochi_server_specs.md`.