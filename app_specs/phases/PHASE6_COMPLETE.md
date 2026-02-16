# Phase 6 Complete: Context Window Management

## Overview

Phase 6 of the mochi-server evolution has been successfully completed. This phase implements dynamic context window management that automatically adjusts based on model capabilities and conversation length, along with a comprehensive status endpoint for session information.

## What Was Implemented

### 1. DynamicContextWindowService

A new service class (`src/mochi_server/services/context_window.py`) that handles context window calculations:

- **Model-aware sizing**: Retrieves model's maximum context length from Ollama API
- **Dynamic adjustment**: Automatically scales context window based on token usage
- **Safety limits**: Uses 90% of model max context as safe limit
- **Buffer management**: Ensures 50% buffer above current usage for ongoing conversations
- **Adjustment history**: Tracks last 10 context window adjustments
- **Manual override**: Supports user-defined context window settings

**Key Constants:**
- `DEFAULT_INITIAL_WINDOW`: 8192 tokens
- `SAFE_LIMIT_PERCENTAGE`: 90%
- `USAGE_THRESHOLD_PERCENTAGE`: 50%
- `MAX_ADJUSTMENT_HISTORY`: 10 entries

### 2. Status Endpoint

New REST endpoint: `GET /api/v1/sessions/{session_id}/status`

Returns comprehensive session state including:
- Session ID, model, and message count
- Context window configuration (dynamic_enabled, current_window, model_max_context, last_adjustment_reason, manual_override)
- Tool settings (enabled, active tools, execution policy)
- Agent settings (enabled agents)
- System prompt file reference
- Conversation summary (if available)

### 3. Chat Integration

Both streaming and non-streaming chat endpoints now:
- Calculate context window before each request
- Pass `num_ctx` option to Ollama
- Update session's context_window_config after each response
- Include context window info in responses

### 4. Session Persistence

The `context_window_config` is now persisted in session metadata:
- `dynamic_enabled`: Whether automatic sizing is active
- `current_window`: Current context window size
- `last_adjustment`: Reason for last adjustment
- `adjustment_history`: List of recent adjustments
- `manual_override`: Whether user manually set the window

## Files Created

| File | Description |
|------|-------------|
| `src/mochi_server/services/context_window.py` | DynamicContextWindowService implementation |
| `src/mochi_server/models/status.py` | Status response Pydantic models |
| `tests/unit/test_context_window.py` | Unit tests for context window service |
| `tests/integration/test_status_api.py` | Integration tests for status endpoint |

## Files Modified

| File | Changes |
|------|---------|
| `src/mochi_server/services/__init__.py` | Added exports for DynamicContextWindowService |
| `src/mochi_server/dependencies.py` | Added get_context_window_service dependency |
| `src/mochi_server/routers/chat.py` | Integrated context window in chat endpoints |
| `src/mochi_server/routers/sessions.py` | Added status endpoint |

## API Usage Examples

### Get Session Status

```bash
curl "http://localhost:8000/api/v1/sessions/a1b2c3d4e5/status"
```

Response:
```json
{
  "session_id": "a1b2c3d4e5",
  "model": "qwen3:14b",
  "message_count": 12,
  "context_window": {
    "dynamic_enabled": true,
    "current_window": 8192,
    "model_max_context": 40960,
    "last_adjustment_reason": "usage_threshold",
    "manual_override": false
  },
  "tools_enabled": true,
  "active_tools": ["add_numbers", "get_current_time"],
  "execution_policy": "always_confirm",
  "agents_enabled": true,
  "enabled_agents": ["coder"],
  "system_prompt_file": "using_agents.md",
  "summary": {
    "summary": "Discussion about Python patterns...",
    "topics": ["python", "design patterns"]
  },
  "summary_model": "qwen3:14b"
}
```

### Chat Response with Context Window

```bash
curl -X POST "http://localhost:8000/api/v1/chat/a1b2c3d4e5" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

Response includes context window info:
```json
{
  "session_id": "a1b2c3d4e5",
  "message": {...},
  "tool_calls_executed": [],
  "context_window": {
    "current_window": 8192,
    "usage_tokens": 165,
    "reason": "usage_threshold"
  }
}
```

## Test Results

All tests pass:
- **Unit tests**: 15 tests for DynamicContextWindowService
- **Integration tests**: 8 tests for status endpoint
- **Total tests**: 235 tests (all passing)
- **Type checks**: All passing
- **Lint checks**: All passing

## Key Implementation Notes

1. **Context Window Calculation Logic**:
   - New conversations: Use `min(safe_limit, 8192)` as initial window
   - Ongoing conversations: Ensure at least 50% buffer above current usage
   - Never exceed 90% of model max context (safe limit)

2. **Adjustment Reasons**:
   - `initial_setup`: First request - set initial context window
   - `usage_threshold`: Usage exceeded threshold - increase window
   - `model_change`: Model changed - recalculate for new model
   - `no_adjustment`: Current window is adequate
   - `manual_override`: User manually set context window

3. **Backward Compatibility**:
   - Default behavior preserves existing functionality
   - When dynamic_enabled is false, no num_ctx is passed to Ollama
   - Session format remains compatible (format version 1.3)

## Next Steps

Phase 6 is complete. The server now supports:
- Dynamic context window management
- Comprehensive session status endpoint
- Context window info in all chat responses

The next phase (Phase 7) will implement the Tool System, enabling function calling capabilities during chat conversations.

---

**Phase 6 Completed**: 2025
**Total Phases**: 9
**Current Progress**: 6/9 phases complete (67%)