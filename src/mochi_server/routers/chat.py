"""Chat API endpoints.

This module provides endpoints for chat interactions with sessions,
including non-streaming and streaming responses via SSE, and tool execution.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from mochi_server.dependencies import (
    get_context_window_service,
    get_ollama_client,
    get_tool_execution_service,
)
from mochi_server.models.chat import (
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    ContextWindowInfo,
    DoneEvent,
    ErrorEvent,
    MessageCompleteEvent,
    MessageResponse,
    ThinkingDeltaEvent,
    ToolCallConfirmationRequiredEvent,
    ToolCallEvent,
    ToolContinuationStartEvent,
    ToolResultEvent,
)
from mochi_server.models.tools import ToolConfirmationRequest, ToolConfirmationResponse
from mochi_server.ollama.client import OllamaClient
from mochi_server.services.context_window import DynamicContextWindowService
from mochi_server.sessions.session import ChatSession
from mochi_server.sessions.types import AssistantMessage, ToolMessage, UserMessage
from mochi_server.tools import ToolExecutionService
from mochi_server.tools.config import requires_confirmation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Global dictionary to store pending confirmations
# Key: confirmation_id, Value: {"event": asyncio.Event, "approved": bool | None, "tool_call": dict}
_pending_confirmations: dict[str, dict] = {}


def _convert_messages_to_ollama_format(messages: list) -> list[dict]:
    """Convert session messages to Ollama API format.

    Args:
        messages: List of message objects (UserMessage, SystemMessage, AssistantMessage, ToolMessage)

    Returns:
        List of message dicts in Ollama format: [{"role": "...", "content": "..."}, ...]
    """
    ollama_messages = []

    for msg in messages:
        # Build basic message structure
        ollama_msg = {
            "role": msg.role,
            "content": msg.content,
        }

        # Add tool_calls for assistant messages that have them
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            ollama_msg["tool_calls"] = msg.tool_calls

        ollama_messages.append(ollama_msg)

    return ollama_messages


async def _collect_streaming_response(
    ollama_client: OllamaClient,
    model: str,
    messages: list[dict],
    options: dict | None = None,
) -> tuple[str, dict]:
    """Collect a complete response from Ollama's streaming API.

    Args:
        ollama_client: The Ollama client instance
        model: Model name to use
        messages: Messages in Ollama format
        options: Optional model parameters (e.g., num_ctx for context window)

    Returns:
        Tuple of (complete_content, final_chunk_metadata)

    Raises:
        HTTPException: If streaming fails
    """
    content_parts = []
    final_chunk = None

    try:
        async for chunk in ollama_client.chat_stream(
            model=model,
            messages=messages,
            options=options,
        ):
            # Accumulate content
            message = chunk.get("message", {})
            content = message.get("content", "")
            if content:
                content_parts.append(content)

            # Keep the final chunk for metadata
            if chunk.get("done"):
                final_chunk = chunk

    except Exception as e:
        logger.error(f"Ollama streaming error: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "ollama_error",
                    "message": f"Failed to get response from Ollama: {str(e)}",
                    "details": {},
                }
            },
        )

    if final_chunk is None:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "incomplete_response",
                    "message": "Stream ended without completion marker",
                    "details": {},
                }
            },
        )

    complete_content = "".join(content_parts)
    return complete_content, final_chunk


@router.post("/{session_id}", response_model=ChatResponse)
async def chat_non_streaming(
    session_id: str,
    request_body: ChatRequest,
    request: Request,
    ollama_client: OllamaClient = Depends(get_ollama_client),
    context_window_service: DynamicContextWindowService = Depends(
        get_context_window_service
    ),
) -> ChatResponse:
    """Send a message to a session and receive a complete response.

    This endpoint uses Ollama's streaming API internally but collects
    all chunks before returning the complete response to the client.

    Message Handling:
        - With message="text": Adds a new user message and generates assistant response
        - With message=null: Continues from existing history without adding user message
          - If last message is user: Regenerates the assistant response
          - If last message is assistant: Continues the conversation (useful for agent loops,
            multi-turn planning, or having the LLM elaborate on its previous output)

    Args:
        session_id: The session ID to chat with
        request_body: Chat request containing message and options
        request: FastAPI request object
        ollama_client: Injected Ollama client

    Returns:
        ChatResponse with the complete assistant message

    Raises:
        HTTPException: 404 if session not found, 502 if Ollama fails

    Examples:
        # New user message
        POST /api/v1/chat/{session_id}
        {"message": "What is Python?"}

        # Regenerate last response
        POST /api/v1/chat/{session_id}
        {"message": null}  # Last message must be user

        # Continue from assistant (agent loop)
        POST /api/v1/chat/{session_id}
        {"message": null}  # Last message is assistant, LLM continues
    """
    # Get settings from app.state to ensure test isolation
    settings = request.app.state.settings
    sessions_dir = settings.resolved_sessions_dir

    # Load the session
    try:
        session = ChatSession.load(session_id, sessions_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "session_not_found",
                    "message": f"Session {session_id} not found",
                    "details": {"session_id": session_id},
                }
            },
        )
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "session_load_error",
                    "message": f"Failed to load session: {str(e)}",
                    "details": {},
                }
            },
        )

    # Add user message if provided
    if request_body.message is not None:
        user_message = UserMessage(
            content=request_body.message,
            message_id=uuid.uuid4().hex[:10],
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        session.add_message(user_message)
        logger.info(f"Added user message to session {session_id}")

    # Convert messages to Ollama format
    ollama_messages = _convert_messages_to_ollama_format(session.messages)

    if not ollama_messages:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "empty_history",
                    "message": "Session has no messages to process",
                    "details": {},
                }
            },
        )

    logger.info(
        f"Sending {len(ollama_messages)} messages to Ollama with model {session.model}"
    )

    # Calculate context window before sending to Ollama
    context_config = session.metadata.context_window_config
    model_max_context = await context_window_service.get_model_max_context(
        session.model
    )

    # Estimate token usage from message count (rough approximation)
    estimated_usage = len(session.messages) * 50  # rough estimate

    calculation = context_window_service.calculate_context_window(
        model=session.model,
        current_window=context_config.current_window,
        dynamic_enabled=context_config.dynamic_enabled,
        manual_override=context_config.manual_override,
        model_max_context=model_max_context,
        usage_tokens=estimated_usage,
        last_adjustment_reason=context_config.last_adjustment,
    )

    # Get num_ctx options to pass to Ollama
    ollama_options = context_window_service.get_num_ctx_options(
        context_window=calculation.current_window,
        dynamic_enabled=context_config.dynamic_enabled,
        manual_override=context_config.manual_override,
    )

    # Get the streaming response and collect it
    content, final_chunk = await _collect_streaming_response(
        ollama_client=ollama_client,
        model=session.model,
        messages=ollama_messages,
        options=ollama_options,
    )

    logger.info(f"Received complete response: {len(content)} characters")

    # Create assistant message
    assistant_message = AssistantMessage(
        content=content,
        model=session.model,
        message_id=uuid.uuid4().hex[:10],
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        eval_count=final_chunk.get("eval_count"),
        prompt_eval_count=final_chunk.get("prompt_eval_count"),
        tool_calls=None,  # Phase 3 doesn't handle tools yet
    )

    # Add assistant message to session
    session.add_message(assistant_message)

    # Update context window config based on actual usage
    prompt_tokens = final_chunk.get("prompt_eval_count", 0)
    eval_tokens = final_chunk.get("eval_count", 0)
    total_tokens = prompt_tokens + eval_tokens

    # Recalculate context window based on actual token usage
    final_calculation = context_window_service.calculate_context_window(
        model=session.model,
        current_window=calculation.current_window,
        dynamic_enabled=context_config.dynamic_enabled,
        manual_override=context_config.manual_override,
        model_max_context=model_max_context,
        usage_tokens=total_tokens,
        last_adjustment_reason=calculation.reason,
    )

    # Update session metadata with new context window config
    session.metadata.context_window_config.current_window = (
        final_calculation.current_window
    )
    session.metadata.context_window_config.last_adjustment = final_calculation.reason

    # Add to adjustment history (keep last 10)
    adjustment_entry = {
        "reason": final_calculation.reason,
        "window": final_calculation.current_window,
        "usage_tokens": total_tokens,
    }
    session.metadata.context_window_config.adjustment_history.append(adjustment_entry)
    if len(session.metadata.context_window_config.adjustment_history) > 10:
        session.metadata.context_window_config.adjustment_history = (
            session.metadata.context_window_config.adjustment_history[-10:]
        )

    # Save the session
    try:
        session.save(sessions_dir)
        logger.debug(f"Saved session {session_id} with new messages")
    except Exception as e:
        logger.error(f"Failed to save session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "session_save_error",
                    "message": f"Failed to save session: {str(e)}",
                    "details": {},
                }
            },
        )

    # Build response
    message_response = MessageResponse(
        role=assistant_message.role,
        content=assistant_message.content,
        model=assistant_message.model,
        message_id=assistant_message.message_id,
        timestamp=assistant_message.timestamp,
        eval_count=assistant_message.eval_count,
        prompt_eval_count=assistant_message.prompt_eval_count,
        tool_calls=assistant_message.tool_calls,
    )

    # Calculate context window info
    # Phase 3: Simple placeholder - full history sent
    prompt_tokens = final_chunk.get("prompt_eval_count", 0)
    eval_tokens = final_chunk.get("eval_count", 0)
    total_tokens = prompt_tokens + eval_tokens

    context_window = ContextWindowInfo(
        current_window=session.metadata.context_window_config.current_window,
        usage_tokens=total_tokens,
        reason=session.metadata.context_window_config.last_adjustment,
    )

    return ChatResponse(
        session_id=session_id,
        message=message_response,
        tool_calls_executed=[],  # Phase 3 doesn't execute tools yet
        context_window=context_window,
    )


@router.post("/{session_id}/stream")
async def chat_streaming(
    session_id: str,
    request_body: ChatRequest,
    request: Request,
    ollama_client: OllamaClient = Depends(get_ollama_client),
    context_window_service: DynamicContextWindowService = Depends(
        get_context_window_service
    ),
    tool_execution_service: ToolExecutionService = Depends(get_tool_execution_service),
) -> EventSourceResponse:
    """Stream a chat response via Server-Sent Events (SSE).

    This endpoint streams the LLM response in real-time as it is generated.
    Events are emitted as they occur: content_delta, thinking_delta (if think=true),
    message_complete, and done.

    Message Handling:
        - With message="text": Adds a new user message and streams assistant response
        - With message=null: Continues from existing history without adding user message
          - If last message is user: Regenerates the assistant response
          - If last message is assistant: Continues the conversation (useful for agent loops,
            multi-turn planning, or having the LLM elaborate on its previous output)

    Args:
        session_id: The session ID to chat with
        request_body: Chat request containing message and options
        request: FastAPI request object
        ollama_client: Injected Ollama client

    Returns:
        EventSourceResponse with SSE events

    SSE Events:
        - content_delta: Each text chunk from the LLM
        - thinking_delta: Each thinking chunk (when think=true)
        - message_complete: Full message metadata after generation
        - error: If an error occurs during streaming
        - done: Stream is complete

    Raises:
        HTTPException: 404 if session not found

    Examples:
        # New user message
        POST /api/v1/chat/{session_id}/stream
        {"message": "Create a plan for a web app"}

        # Continue from assistant (agent loop pattern)
        POST /api/v1/chat/{session_id}/stream
        {"message": null}  # LLM continues elaborating or executing plan
    """
    # Get settings from app.state to ensure test isolation
    settings = request.app.state.settings
    sessions_dir = settings.resolved_sessions_dir

    # Load the session
    try:
        session = ChatSession.load(session_id, sessions_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "session_not_found",
                    "message": f"Session {session_id} not found",
                    "details": {"session_id": session_id},
                }
            },
        )
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "session_load_error",
                    "message": f"Failed to load session: {str(e)}",
                    "details": {},
                }
            },
        )

    # Add user message if provided
    if request_body.message is not None:
        user_message = UserMessage(
            content=request_body.message,
            message_id=uuid.uuid4().hex[:10],
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        session.add_message(user_message)
        logger.info(f"Added user message to session {session_id}")

    # Convert messages to Ollama format
    ollama_messages = _convert_messages_to_ollama_format(session.messages)

    if not ollama_messages:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "empty_history",
                    "message": "Session has no messages to process",
                    "details": {},
                }
            },
        )

    logger.info(
        f"Starting streaming chat for session {session_id} with {len(ollama_messages)} messages"
    )

    # Calculate context window before streaming
    context_config = session.metadata.context_window_config
    model_max_context = await context_window_service.get_model_max_context(
        session.model
    )

    # Estimate token usage
    estimated_usage = len(session.messages) * 50

    calculation = context_window_service.calculate_context_window(
        model=session.model,
        current_window=context_config.current_window,
        dynamic_enabled=context_config.dynamic_enabled,
        manual_override=context_config.manual_override,
        model_max_context=model_max_context,
        usage_tokens=estimated_usage,
        last_adjustment_reason=context_config.last_adjustment,
    )

    # Get num_ctx options
    ollama_options = context_window_service.get_num_ctx_options(
        context_window=calculation.current_window,
        dynamic_enabled=context_config.dynamic_enabled,
        manual_override=context_config.manual_override,
    )

    # Get tool settings and schemas
    tool_settings = session.metadata.tool_settings
    active_tools = tool_settings.tools or []
    execution_policy = tool_settings.execution_policy
    tool_group = tool_settings.tool_group

    # Get tool schemas if tools are enabled
    tools = None
    if active_tools or tool_group:
        # Import here to avoid circular imports
        from mochi_server.dependencies import get_tool_schema_service

        tool_schema_service = get_tool_schema_service(request)
        all_schemas = tool_schema_service.get_all_tool_schemas()

        # Filter to active tools
        if active_tools:
            tools = [
                all_schemas.get(name) for name in active_tools if name in all_schemas
            ]
            tools = [t for t in tools if t is not None]
        elif tool_group:
            # Get all tools in the group
            discovery_service = request.app.state.tool_discovery_service
            groups = discovery_service.get_tool_groups() if discovery_service else {}
            group_tools = groups.get(tool_group, [])
            tools = [
                all_schemas.get(name) for name in group_tools if name in all_schemas
            ]
            tools = [t for t in tools if t is not None]

    async def event_generator():
        """Generate SSE events from Ollama streaming response."""
        content_parts = []
        thinking_parts = []
        final_chunk = None
        message_id = uuid.uuid4().hex[:10]
        assistant_tool_calls = None

        # Track tool calls executed in this response for reporting
        tool_calls_executed = []

        try:
            # Stream from Ollama
            async for chunk in ollama_client.chat_stream(
                model=session.model,
                messages=ollama_messages,
                options=ollama_options,
                tools=tools,
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.warning(
                        f"Client disconnected during streaming for session {session_id}"
                    )
                    break

                message = chunk.get("message", {})
                content = message.get("content", "")

                # Emit content delta if there's content
                if content:
                    content_parts.append(content)
                    event_data = ContentDeltaEvent(
                        content=content,
                        role=message.get("role", "assistant"),
                    )
                    yield {
                        "event": "content_delta",
                        "data": event_data.model_dump_json(),
                    }

                # Keep final chunk for metadata and check for tool calls
                if chunk.get("done"):
                    final_chunk = chunk
                    # Check if the response has tool calls
                    message = chunk.get("message", {})
                    if message.get("tool_calls"):
                        assistant_tool_calls = message["tool_calls"]
                    break

                # Also check for tool calls in non-final chunks
                message = chunk.get("message", {})
                if message.get("tool_calls"):
                    assistant_tool_calls = message["tool_calls"]

            # Handle tool calls if present
            if assistant_tool_calls:
                logger.info(
                    f"Received {len(assistant_tool_calls)} tool calls from model"
                )

                # Process each tool call
                for tool_call in assistant_tool_calls:
                    tool_name = tool_call.get("function", {}).get("name", "")
                    arguments = tool_call.get("function", {}).get("arguments", {})

                    # Handle case where arguments is a string (JSON)
                    if isinstance(arguments, str):
                        import json

                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                    tool_call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}")

                    # Check if confirmation is required
                    if requires_confirmation(execution_policy):
                        # Emit confirmation required event
                        confirmation_id = f"conf_{uuid.uuid4().hex[:12]}"
                        confirmation_event = ToolCallConfirmationRequiredEvent(
                            confirmation_id=confirmation_id,
                            tool_name=tool_name,
                            arguments=arguments,
                        )
                        yield {
                            "event": "tool_call_confirmation_required",
                            "data": confirmation_event.model_dump_json(),
                        }

                        # Store pending confirmation
                        event = asyncio.Event()
                        _pending_confirmations[confirmation_id] = {
                            "event": event,
                            "approved": None,
                            "tool_call": tool_call,
                        }

                        # Wait for client confirmation (no timeout - client must respond)
                        await event.wait()

                        # Get result
                        pending = _pending_confirmations.pop(confirmation_id, {})
                        approved = pending.get("approved", False)

                        if approved:
                            # Execute the tool
                            from mochi_server.dependencies import (
                                get_tool_execution_service,
                            )

                            execution_service = get_tool_execution_service(request)
                            result = execution_service.execute_tool(
                                tool_name, arguments
                            )

                            # Emit tool result event
                            result_event = ToolResultEvent(
                                tool_name=tool_name,
                                result=result.result,
                                success=result.success,
                                error=result.error,
                            )
                            yield {
                                "event": "tool_result",
                                "data": result_event.model_dump_json(),
                            }

                            # Add tool message to session
                            tool_message = ToolMessage(
                                tool_name=tool_name,
                                content=result.result,
                                message_id=uuid.uuid4().hex[:10],
                                timestamp=datetime.now(timezone.utc)
                                .isoformat()
                                .replace("+00:00", "Z"),
                            )
                            session.add_message(tool_message)
                            ollama_messages.append(
                                {
                                    "role": "tool",
                                    "tool_name": tool_name,
                                    "content": result.result,
                                }
                            )

                            tool_calls_executed.append(
                                {
                                    "name": tool_name,
                                    "arguments": arguments,
                                    "success": result.success,
                                }
                            )
                        else:
                            # Tool was denied - add denied message
                            denied_message = f"Tool '{tool_name}' was denied by user"
                            tool_message = ToolMessage(
                                tool_name=tool_name,
                                content=denied_message,
                                message_id=uuid.uuid4().hex[:10],
                                timestamp=datetime.now(timezone.utc)
                                .isoformat()
                                .replace("+00:00", "Z"),
                            )
                            session.add_message(tool_message)
                            ollama_messages.append(
                                {
                                    "role": "tool",
                                    "tool_name": tool_name,
                                    "content": denied_message,
                                }
                            )
                    else:
                        # Auto-execute (never_confirm or no policy set)
                        # Emit tool call event
                        tool_event = ToolCallEvent(
                            tool_name=tool_name,
                            arguments=arguments,
                            tool_call_id=tool_call_id,
                        )
                        yield {
                            "event": "tool_call",
                            "data": tool_event.model_dump_json(),
                        }

                        # Execute the tool
                        from mochi_server.dependencies import get_tool_execution_service

                        execution_service = get_tool_execution_service(request)
                        result = execution_service.execute_tool(tool_name, arguments)

                        # Emit tool result event
                        result_event = ToolResultEvent(
                            tool_name=tool_name,
                            result=result.result,
                            success=result.success,
                            error=result.error,
                        )
                        yield {
                            "event": "tool_result",
                            "data": result_event.model_dump_json(),
                        }

                        # Add tool message to session
                        tool_message = ToolMessage(
                            tool_name=tool_name,
                            content=result.result,
                            message_id=uuid.uuid4().hex[:10],
                            timestamp=datetime.now(timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z"),
                        )
                        session.add_message(tool_message)
                        ollama_messages.append(
                            {
                                "role": "tool",
                                "tool_name": tool_name,
                                "content": result.result,
                            }
                        )

                        tool_calls_executed.append(
                            {
                                "name": tool_name,
                                "arguments": arguments,
                                "success": result.success,
                            }
                        )

                # Emit continuation start event
                continuation_event = ToolContinuationStartEvent(
                    tool_count=len(tool_calls_executed),
                )
                yield {
                    "event": "tool_continuation_start",
                    "data": continuation_event.model_dump_json(),
                }

                # Continue conversation with tool results
                # Stream the continuation response
                async for chunk in ollama_client.chat_stream(
                    model=session.model,
                    messages=ollama_messages,
                    options=ollama_options,
                ):
                    # Check if client disconnected
                    if await request.is_disconnected():
                        logger.warning(
                            f"Client disconnected during tool continuation for session {session_id}"
                        )
                        break

                    message = chunk.get("message", {})
                    content = message.get("content", "")
                    thinking = message.get("thinking", "")

                    # Emit thinking if present
                    if thinking:
                        thinking_parts.append(thinking)
                        event_data = ThinkingDeltaEvent(content=thinking)
                        yield {
                            "event": "thinking_delta",
                            "data": event_data.model_dump_json(),
                        }

                    # Emit content if present
                    if content:
                        content_parts.append(content)
                        event_data = ContentDeltaEvent(
                            content=content,
                            role=message.get("role", "assistant"),
                        )
                        yield {
                            "event": "content_delta",
                            "data": event_data.model_dump_json(),
                        }

                    # Keep final chunk
                    if chunk.get("done"):
                        final_chunk = chunk
                        # Check for more tool calls (multi-turn)
                        if message.get("tool_calls"):
                            assistant_tool_calls = message["tool_calls"]
                        break

            # Assemble complete message
            complete_content = "".join(content_parts)
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            # Create and save assistant message
            assistant_message = AssistantMessage(
                content=complete_content,
                model=session.model,
                message_id=message_id,
                timestamp=timestamp,
                eval_count=final_chunk.get("eval_count") if final_chunk else None,
                prompt_eval_count=final_chunk.get("prompt_eval_count")
                if final_chunk
                else None,
                tool_calls=assistant_tool_calls,
            )

            session.add_message(assistant_message)

            # Update context window config based on actual usage
            prompt_tokens = (
                final_chunk.get("prompt_eval_count", 0) if final_chunk else 0
            )
            eval_tokens = final_chunk.get("eval_count", 0) if final_chunk else 0
            total_tokens = prompt_tokens + eval_tokens

            # Recalculate context window based on actual token usage
            final_calculation = context_window_service.calculate_context_window(
                model=session.model,
                current_window=calculation.current_window,
                dynamic_enabled=context_config.dynamic_enabled,
                manual_override=context_config.manual_override,
                model_max_context=model_max_context,
                usage_tokens=total_tokens,
                last_adjustment_reason=calculation.reason,
            )

            # Update session metadata with new context window config
            session.metadata.context_window_config.current_window = (
                final_calculation.current_window
            )
            session.metadata.context_window_config.last_adjustment = (
                final_calculation.reason
            )

            # Add to adjustment history
            adjustment_entry = {
                "reason": final_calculation.reason,
                "window": final_calculation.current_window,
                "usage_tokens": total_tokens,
            }
            session.metadata.context_window_config.adjustment_history.append(
                adjustment_entry
            )
            if len(session.metadata.context_window_config.adjustment_history) > 10:
                session.metadata.context_window_config.adjustment_history = (
                    session.metadata.context_window_config.adjustment_history[-10:]
                )

            # Save session
            try:
                session.save(sessions_dir)
                logger.debug(f"Saved session {session_id} after streaming")
            except Exception as e:
                logger.error(f"Failed to save session {session_id}: {e}")
                error_event = ErrorEvent(
                    code="session_save_error",
                    message=f"Failed to save session: {str(e)}",
                    details={},
                )
                yield {
                    "event": "error",
                    "data": error_event.model_dump_json(),
                }
                return

            # Calculate context window info (tokens already calculated above)
            context_window = ContextWindowInfo(
                current_window=session.metadata.context_window_config.current_window,
                usage_tokens=total_tokens,
                reason=session.metadata.context_window_config.last_adjustment,
            )

            # Emit message_complete event
            complete_event = MessageCompleteEvent(
                message_id=message_id,
                model=session.model,
                eval_count=assistant_message.eval_count,
                prompt_eval_count=assistant_message.prompt_eval_count,
                context_window=context_window,
            )
            yield {
                "event": "message_complete",
                "data": complete_event.model_dump_json(),
            }

            # Emit done event
            done_event = DoneEvent(session_id=session_id)
            yield {
                "event": "done",
                "data": done_event.model_dump_json(),
            }

        except Exception as e:
            logger.error(f"Error during streaming for session {session_id}: {e}")
            error_event = ErrorEvent(
                code="ollama_error",
                message=f"Failed to generate response: {str(e)}",
                details={"session_id": session_id},
            )
            yield {
                "event": "error",
                "data": error_event.model_dump_json(),
            }

    return EventSourceResponse(event_generator())


@router.post(
    "/{session_id}/confirm-tool",
    response_model=ToolConfirmationResponse,
    summary="Confirm or deny a tool call",
)
async def confirm_tool(
    session_id: str,
    request_body: ToolConfirmationRequest,
) -> ToolConfirmationResponse:
    """Confirm or deny a pending tool call.

    This endpoint is used to respond to tool_call_confirmation_required events
    emitted during streaming when the session's execution policy is set to
    always_confirm.

    The client receives a confirmation_id in the tool_call_confirmation_required
    event and uses it here to approve or deny the tool execution.

    Args:
        session_id: The session ID
        request_body: Contains confirmation_id and approved flag

    Returns:
        ToolConfirmationResponse with the result

    Raises:
        HTTPException: 404 if confirmation_id not found
    """
    confirmation_id = request_body.confirmation_id
    approved = request_body.approved

    if confirmation_id not in _pending_confirmations:
        logger.warning(f"Confirmation ID not found: {confirmation_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "confirmation_not_found",
                    "message": f"Confirmation ID '{confirmation_id}' not found or expired",
                    "details": {"confirmation_id": confirmation_id},
                }
            },
        )

    # Get the pending confirmation
    pending = _pending_confirmations[confirmation_id]
    tool_call = pending["tool_call"]
    tool_name = tool_call.get("function", {}).get("name", "unknown")

    # Set the result and signal the waiting stream
    pending["approved"] = approved
    pending["event"].set()

    # Clean up
    del _pending_confirmations[confirmation_id]

    if approved:
        logger.info(f"Tool {tool_name} approved for session {session_id}")
        return ToolConfirmationResponse(
            success=True,
            tool_name=tool_name,
            message=f"Tool '{tool_name}' execution approved",
        )
    else:
        logger.info(f"Tool {tool_name} denied for session {session_id}")
        return ToolConfirmationResponse(
            success=True,
            tool_name=tool_name,
            message=f"Tool '{tool_name}' execution denied",
        )
