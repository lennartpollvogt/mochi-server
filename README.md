# Mochi Server

A FastAPI-based server application that integrates with [Ollama](https://github.com/ollama/ollama) to provide chat functionality with support for tools. Mochi-server enables LLMs to execute Python functions during conversations.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Directory Structure](#directory-structure)
- [API Endpoints](#api-endpoints)
- [Tools Feature](#tools-feature)
  - [How Tools Work](#how-tools-work)
  - [Writing Your Own Tools](#writing-your-own-tools)
  - [Tool Groups](#tool-groups)
  - [Execution Policies](#execution-policies)
  - [Best Practices](#best-practices)
- [Context Window Management](#context-window-management)
- [Summarization](#summarization)
- [Examples](#examples)

---

## Overview

Mochi-server provides a REST API with Server-Sent Events (SSE) streaming for chat interactions with Ollama. Key features include:

- **Chat API**: Stream responses from Ollama models with full conversation history
- **Tools System**: Define Python functions that LLMs can invoke during conversations
- **Session Management**: Persistent chat sessions stored as JSON files
- **Context Window Management**: Dynamic context window adjustment to prevent token overflow
- **Context Window Management**: Dynamic context window adjustment to prevent token overflow

---

## Installation

### Prerequisites

- Python 3.11+
- [Ollama](https://github.com/ollama/ollama) running locally or remotely

### Install from Source

```bash
# Clone the repository
cd mochi-server

# Install dependencies
pip install -e .

# Or with uv
uv pip install -e .
```

### Install Development Dependencies

```bash
pip install -e ".[dev]"
# or with uv
uv sync --group dev
```

---

## Quick Start

### 1. Start Ollama

Ensure Ollama is running:

```bash
# Start Ollama in the background
ollama serve

# Pull a model (if not already installed)
ollama pull llama3.2
```

### 2. Start Mochi Server

```bash
# Using the installed command
mochi-server

# Or with Python
python -m mochi_server
```

The server will start on `http://127.0.0.1:8000` by default.

### 3. Verify Health

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "ollama_connected": true,
  "ollama_host": "http://localhost:11434",
  "version": "0.1.0"
}
```

---

## Configuration

### Environment Variables

All configuration is handled via environment variables with the `MOCHI_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCHI_HOST` | `127.0.0.1` | Server bind address |
| `MOCHI_PORT` | `8000` | Server bind port |
| `MOCHI_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `MOCHI_DATA_DIR` | `.` | Base directory for all data |
| `MOCHI_SESSIONS_DIR` | `chat_sessions` | Session storage directory |
| `MOCHI_TOOLS_DIR` | `tools` | Tools directory |
| `MOCHI_SYSTEM_PROMPTS_DIR` | `system_prompts` | System prompts directory |
| `MOCHI_SUMMARIZATION_ENABLED` | `true` | Reserved for future use (not yet implemented) |
| `MOCHI_DYNAMIC_CONTEXT_WINDOW_ENABLED` | `true` | Enable dynamic context window |
| `MOCHI_CORS_ORIGINS` | `["*"]` | Allowed CORS origins |
| `MOCHI_LOG_LEVEL` | `INFO` | Logging level |

**Note:** The following settings exist but are reserved for future use:
- `MOCHI_AGENTS_DIR` - For future agent system
- `MOCHI_AGENT_CHATS_DIR` - For future agent chat sessions
- `MOCHI_MAX_AGENT_ITERATIONS` - For future agent loops

### Configuration Examples

#### Change Host and Port

```bash
export MOCHI_HOST=0.0.0.0
export MOCHI_PORT=9000
mochi-server
```

#### Connect to Remote Ollama

```bash
export MOCHI_OLLAMA_HOST=http://192.168.1.100:11434
mochi-server
```

#### Custom Data Directory

```bash
export MOCHI_DATA_DIR=/var/lib/mochi
export MOCHI_SESSIONS_DIR=sessions
export MOCHI_TOOLS_DIR=tools
```

#### Debug Mode

```bash
export MOCHI_LOG_LEVEL=DEBUG
mochi-server
```

### Directory Structure

The server uses the following directory structure (relative to `MOCHI_DATA_DIR`):

```
{data_dir}/
├── chat_sessions/           # User chat session files
├── tools/                   # Tool definitions
│   ├── __init__.py          # Tool exports and groups
│   ├── math_tools.py       # Tool implementations
│   └── ...
└── system_prompts/          # System prompt files
```

---

## API Endpoints

### Health & Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Server health check |
| GET | `/api/v1/models` | List available Ollama models |
| GET | `/api/v1/models/{model_name}` | Get model details |
| GET | `/api/v1/sessions/{session_id}/status` | Context window and session status |

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/sessions` | List all chat sessions |
| POST | `/api/v1/sessions` | Create a new session |
| GET | `/api/v1/sessions/{session_id}` | Get session details |
| DELETE | `/api/v1/sessions/{session_id}` | Delete a session |
| GET | `/api/v1/sessions/{session_id}/messages` | Get session messages |
| DELETE | `/api/v1/sessions/{session_id}/system-prompt` | Remove session system prompt |

### Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/{session_id}` | Send message (non-streaming) |
| POST | `/api/v1/chat/{session_id}/stream` | Stream chat response (SSE) |
| POST | `/api/v1/chat/{session_id}/confirm-tool` | Confirm/deny tool call |

### Tools

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tools` | List all discovered tools |
| GET | `/api/v1/tools/{tool_name}` | Get tool details |
| POST | `/api/v1/tools/reload` | Reload tools from disk |

### System Prompts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/system-prompts` | List system prompts |
| GET | `/api/v1/system-prompts/{filename}` | Get prompt content |
| POST | `/api/v1/system-prompts/{filename}` | Create/update prompt |
| DELETE | `/api/v1/system-prompts/{filename}` | Delete prompt |

---

## Tools Feature

### How Tools Work

Tools are Python functions that LLMs can call during conversations. When an LLM decides to use a tool:

1. The LLM returns a response with `tool_calls`
2. The tool is executed (either automatically or after confirmation)
3. The tool result is added to the conversation
4. The LLM receives the result and continues the conversation

### Writing Your Own Tools

Tools are defined as Python functions in the `tools_dir`. Here's an example:

```python
# tools/math_tools.py

def add_numbers(a: int, b: int) -> str:
    """
    Add two numbers together.

    Args:
        a (int): The first number
        b (int): The second number

    Returns:
        str: The sum of the two numbers
    """
    return str(a + b)


def multiply_numbers(a: float, b: float) -> str:
    """
    Multiply two numbers together.

    Args:
        a (float): The first number
        b (float): The second number

    Returns:
        str: The product of the two numbers
    """
    return str(a * b)
```

### Tool Requirements

Every tool function **must** meet these requirements:

1. **Type hints** on all parameters and return type
2. **Docstring** describing the function (used for schema generation)
3. **Return a string** (the result converted to string for LLM consumption)

### Tool Groups

Define tool groups in `tools/__init__.py` using double-underscore variables:

```python
# tools/__init__.py
from .math_tools import add_numbers, multiply_numbers
from .utility_tools import get_current_time, flip_coin

# Export all tools
__all__ = ["add_numbers", "multiply_numbers", "get_current_time", "flip_coin"]

# Define tool groups
__math__ = ["add_numbers", "multiply_numbers"]
__utilities__ = ["get_current_time", "flip_coin"]
```

### Enabling Tools in a Session

When creating a session, specify tool settings:

```json
{
  "model": "llama3.2",
  "tool_settings": {
    "tools": ["add_numbers", "multiply_numbers"],
    "execution_policy": "never_confirm"
  }
}
```

Or use tool groups:

```json
{
  "model": "llama3.2",
  "tool_settings": {
    "tool_group": "math",
    "execution_policy": "always_confirm"
  }
}
```

### Execution Policies

| Policy | Description |
|--------|-------------|
| `never_confirm` | Execute tools automatically without user confirmation |
| `always_confirm` | Require user confirmation before executing each tool |

When confirmation is required, the server emits a `tool_call_confirmation_required` event with a `confirmation_id`. The client must then call:

```bash
curl -X POST "http://localhost:8000/api/v1/chat/{session_id}/confirm-tool" \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id": "conf_abc123", "approved": true}'
```

### Best Practices

When writing tools for mochi-server, follow these best practices:

#### 1. Use Clear, Descriptive Names

```python
# Good
def calculate_compound_interest(principal: float, rate: float, years: float) -> str:
    """Calculate compound interest with annual compounding."""

# Bad
def calc(p: float, r: float, t: float) -> str:
    """Calculate something."""
```

#### 2. Write Comprehensive Docstrings

The docstring is used to generate the tool schema. Include:
- What the tool does
- Description of each parameter
- What the return value represents

```python
def get_weather(city: str, units: str = "celsius") -> str:
    """
    Get the current weather for a city.

    Args:
        city (str): The name of the city (e.g., "London", "Tokyo")
        units (str): Temperature units - "celsius" or "fahrenheit" (default: "celsius")

    Returns:
        str: A string describing the current weather conditions and temperature
    """
    # Implementation...
```

#### 3. Always Return Strings

The LLM expects string responses. Convert your return value explicitly:

```python
# Good
def add(a: int, b: int) -> str:
    return str(a + b)

def get_user_count() -> str:
    return str(len(users))  # Explicit conversion
```

#### 4. Handle Errors Gracefully

Return error messages as strings rather than raising exceptions:

```python
def divide(a: float, b: float) -> str:
    """
    Divide two numbers.

    Args:
        a (float): The dividend
        b (float): The divisor

    Returns:
        str: The result or an error message
    """
    if b == 0:
        return "Error: Cannot divide by zero"
    return str(a / b)
```

#### 5. Use Appropriate Types

Use specific types rather than generic ones when possible:

```python
# Good
def process_items(items: list[str], max_count: int | None = None) -> str:

# Avoid
def process_items(items: list, max_count: int = None) -> str:
```

#### 6. Keep Tools Focused

Each tool should do one thing well. Don't create monolithic tools:

```python
# Good - separate concerns
def get_stock_price(symbol: str) -> str:
    """Get the current stock price."""

def get_stock_volume(symbol: str) -> str:
    """Get the trading volume."""

# Avoid
def get_stock_info(symbol: str) -> str:
    """Get all stock information including price, volume, market cap, etc."""
```

#### 7. Consider LLM Context

Remember that the LLM sees the tool schema and docstring. Make sure the descriptions help the LLM understand when to use each tool:

```python
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Convert an amount from one currency to another.
    Use this when the user asks about currency exchange rates or conversions.

    Args:
        amount (float): The amount to convert
        from_currency (str): The source currency code (e.g., "USD", "EUR")
        to_currency (str): The target currency code (e.g., "GBP", "JPY")

    Returns:
        str: The converted amount with exchange rate info
    """
```

#### 8. Validate Input When Necessary

```python
def calculate_fibonacci(n: int) -> str:
    """
    Calculate the nth Fibonacci number.

    Args:
        n (int): The position in the Fibonacci sequence (must be positive)

    Returns:
        str: The nth Fibonacci number
    """
    if n <= 0:
        return "Error: n must be a positive integer"
    if n > 1000:
        return "Error: n is too large (max 1000)"
    
    # Implementation...
```

---

## Context Window Management

Mochi-server manages context window dynamically to prevent token overflow:

- **Dynamic adjustment** (enabled by default): Automatically reduces context when approaching limits
- **Manual override**: Can set a fixed context window per session

Configure via session creation or the `/sessions/{session_id}/status` endpoint:

```json
{
  "model": "llama3.2",
  "context_window": {
    "dynamic_enabled": true,
    "current_window": 4096,
    "manual_override": null
  }
}
```

---

## Summarization

**Not yet implemented.** This feature is planned for Phase 9.

The configuration option `MOCHI_SUMMARIZATION_ENABLED` exists but is currently unused.

---

## Examples

### Create a New Session

```bash
curl -X POST "http://localhost:8000/api/v1/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "system_prompt": "You are a helpful assistant."
  }'
```

### Stream Chat

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/{session_id}/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'
```

### List Available Tools

```bash
curl http://localhost:8000/api/v1/tools
```

Response:

```json
{
  "tools": [
    {
      "name": "add_numbers",
      "description": "Add two numbers together.",
      "parameters": {
        "type": "object",
        "properties": {
          "a": {"type": "integer", "description": "The first number"},
          "b": {"type": "integer", "description": "The second number"}
        },
        "required": ["a", "b"]
      }
    }
  ],
  "groups": {
    "math": ["add_numbers", "multiply_numbers"],
    "utilities": ["get_current_time", "flip_coin"]
  }
}
```

### Chat with Tools

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/{session_id}/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is 25 + 17?",
    "tool_settings": {
      "tools": ["add_numbers"],
      "execution_policy": "never_confirm"
    }
  }'
```

### List System Prompts

```bash
curl http://localhost:8000/api/v1/system-prompts
```

### Get Session Status

```bash
curl http://localhost:8000/api/v1/sessions/{session_id}/status
```

---

## License

MIT License