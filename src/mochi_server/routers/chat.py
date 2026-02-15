"""Chat API endpoints.

This module provides endpoints for chat interactions with sessions,
including non-streaming and streaming responses via SSE.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from mochi_server.dependencies import get_ollama_client
from mochi_server.models.chat import (
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    ContextWindowInfo,
    DoneEvent,
    ErrorEvent,
    MessageCompleteEvent,
    MessageResponse,
)
from mochi_server.ollama.client import OllamaClient
from mochi_server.sessions.session import ChatSession
from mochi_server.sessions.types import AssistantMessage, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


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
) -> tuple[str, dict]:
    """Collect a complete response from Ollama's streaming API.

    Args:
        ollama_client: The Ollama client instance
        model: Model name to use
        messages: Messages in Ollama format

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
) -> ChatResponse:
    """Send a message to a session and receive a complete response.

    This endpoint uses Ollama's streaming API internally but collects
    all chunks before returning the complete response to the client.

    Args:
        session_id: The session ID to chat with
        request_body: Chat request containing message and options
        request: FastAPI request object
        ollama_client: Injected Ollama client

    Returns:
        ChatResponse with the complete assistant message

    Raises:
        HTTPException: 404 if session not found, 502 if Ollama fails
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

    # Get the streaming response and collect it
    content, final_chunk = await _collect_streaming_response(
        ollama_client=ollama_client,
        model=session.model,
        messages=ollama_messages,
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
) -> EventSourceResponse:
    """Stream a chat response via Server-Sent Events (SSE).

    This endpoint streams the LLM response in real-time as it is generated.
    Events are emitted as they occur: content_delta, thinking_delta (if think=true),
    message_complete, and done.

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

    async def event_generator():
        """Generate SSE events from Ollama streaming response."""
        content_parts = []
        final_chunk = None
        message_id = uuid.uuid4().hex[:10]

        try:
            # Stream from Ollama
            async for chunk in ollama_client.chat_stream(
                model=session.model,
                messages=ollama_messages,
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

                # Keep final chunk for metadata
                if chunk.get("done"):
                    final_chunk = chunk
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
                tool_calls=None,  # Phase 4 doesn't handle tools yet
            )

            session.add_message(assistant_message)

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

            # Calculate context window info
            prompt_tokens = (
                final_chunk.get("prompt_eval_count", 0) if final_chunk else 0
            )
            eval_tokens = final_chunk.get("eval_count", 0) if final_chunk else 0
            total_tokens = prompt_tokens + eval_tokens

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
