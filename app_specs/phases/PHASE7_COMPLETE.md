# Phase 7 Complete: Tool System

## Overview

Phase 7 implements the Tool System for mochi-server, enabling:
- Discovery of Python functions as tools from a configurable directory
- Conversion of tools to Ollama-compatible schemas
- Tool execution during chat (both auto-execute and confirmation flows)
- Real-time SSE events for tool call progress

## Implementation Status: COMPLETE

## New Files Created

### Tool Services (`src/mochi_server/tools/`)

| File | Description |
|------|-------------|
| `config.py` | ToolExecutionPolicy enum and requires_confirmation() function |
| `discovery.py` | ToolDiscoveryService for scanning tools directory and loading tool modules |
| `schema.py` | ToolSchemaService for converting Python functions to Ollama tool schemas |
| `execution.py` | ToolExecutionService for executing tools and handling results |

### Models (`src/mochi_server/models/`)

| File | Description |
|------|-------------|
| `tools.py` | Pydantic models: ToolDetails, ToolListResponse, ToolReloadResponse, ToolConfirmationRequest, ToolConfirmationResponse |

### Routers (`src/mochi_server/routers/`)

| File | Description |
|------|-------------|
| `tools.py` | Tools API endpoints: GET /tools, GET /tools/{name}, POST /tools/reload |

### Test Fixtures

| File | Description |
|------|-------------|
| `tests/fixtures/sample_tools/__init__.py` | Sample math tools module |
| `tests/fixtures/sample_tools/utilities/__init__.py` | Sample utility tools module |

## Modified Files

| File | Changes |
|------|---------|
| `app.py` | Added tool services initialization in lifespan; registered tools router |
| `dependencies.py` | Added get_tool_discovery_service(), get_tool_schema_service(), get_tool_execution_service() |
| `models/chat.py` | Added SSE event schemas: ToolCallEvent, ToolCallConfirmationRequiredEvent, ToolResultEvent, ToolContinuationStartEvent |
| `routers/chat.py` | Added tool execution in streaming chat; added POST /chat/{session_id}/confirm-tool endpoint |
| `ollama/client.py` | Added tools parameter to chat_stream() method |

## New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/tools | List all discovered tools and groups |
| GET | /api/v1/tools/{tool_name} | Get details for a specific tool |
| POST | /api/v1/tools/reload | Force reload tools from disk |
| POST | /api/v1/chat/{session_id}/confirm-tool | Approve or deny a pending tool call |

## SSE Events Added

| Event | Description |
|-------|-------------|
| tool_call | Emitted when LLM requests a tool (auto-execute policy) |
| tool_call_confirmation_required | Emitted when LLM requests a tool (always_confirm policy) |
| tool_result | Emitted after tool execution completes |
| tool_continuation_start | Emitted before sending tool results back to LLM |

## Key Implementation Details

### Tool Discovery
- Scans configured tools_dir for subdirectories
- Each subdirectory must contain __init__.py
- Reads __all__ list to find exported functions
- Validates: callable + has docstring
- Extracts __group__ for tool grouping

### Tool Schema Conversion
- Uses ollama._utils.convert_function_to_tool() for Ollama-compatible schemas
- Falls back to manual schema generation from docstring if Ollama utils unavailable
- Schema caching for performance

### Tool Execution Flow

**Auto-execute (never_confirm policy):**
1. Ollama returns response with tool_calls
2. Emit tool_call SSE event
3. Execute tool immediately
4. Emit tool_result SSE event
5. Add tool message to session
6. Emit tool_continuation_start event
7. Send updated history (with tool results) to Ollama
8. Stream continuation response

**Confirmation (always_confirm policy):**
1. Ollama returns response with tool_calls
2. Emit tool_call_confirmation_required with confirmation_id
3. Stream pauses, waiting for client callback
4. Client calls POST /chat/{id}/confirm-tool
5. If approved: execute tool and continue as above
6. If denied: add denial message and continue

### Confirmation State
- Stored in-memory dictionary: _pending_confirmations
- Key: confirmation_id, Value: {event, approved, tool_call}
- No server-side timeout (client responsible for responding)

## Testing Status

### Existing Tests
- All 156 unit tests: PASS
- All 79 integration tests: PASS

### Phase 7 Tests (Not Yet Implemented)
- Unit tests for tool discovery, schema, execution, config
- Integration tests for tool API
- Integration tests for chat with tools

Test specification available at: tests/PHASE7_TESTS_SPEC.md

## Configuration

Tools are configured via session's tool_settings:
- tools: list of tool names to enable
- tool_group: enable all tools in a group
- execution_policy: "always_confirm" | "never_confirm" | "auto"

## Usage Example

```bash
# List discovered tools
curl http://localhost:8000/api/v1/tools

# Chat with auto-execute tools
curl -N -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2 + 3?"}'

# Confirm a tool call (after receiving confirmation_id)
curl -X POST "http://localhost:8000/api/v1/chat/$SESSION_ID/confirm-tool" \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id": "conf_abc123", "approved": true}'
```

## Dependencies Added

No new runtime dependencies. Uses existing:
- ollama SDK (for schema conversion)
- sse-starlette (already used for streaming)

## Notes

- Tool execution results are always converted to strings for LLM consumption
- Session's tool_settings determine which tools are active and execution policy
- The confirmation flow uses asyncio.Event for blocking until client responds
- Multiple tool calls in a single response are processed in parallel
- Multi-turn tool calling (tool calls in continuation) is supported