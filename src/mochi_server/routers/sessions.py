"""Sessions router for chat session CRUD operations.

This module provides REST API endpoints for:
- Creating new sessions
- Listing all sessions
- Retrieving session details
- Updating session metadata
- Deleting sessions
- Getting session messages
- Setting/removing system prompts on sessions
"""

import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mochi_server.dependencies import (
    get_context_window_service,
    get_session_manager,
    get_system_prompt_service,
)
from mochi_server.models.status import ContextWindowStatus, SessionStatusResponse
from mochi_server.services.context_window import DynamicContextWindowService
from mochi_server.models.sessions import (
    AgentSettingsResponse,
    CreateSessionRequest,
    EditMessageRequest,
    MessageResponse,
    MessagesResponse,
    SessionDetailResponse,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
    SummaryResponse,
    ToolSettingsResponse,
    UpdateSessionRequest,
)
from mochi_server.models.system_prompts import SetSessionSystemPromptRequest
from mochi_server.services import SystemPromptService
from mochi_server.sessions import (
    AgentSettings,
    SessionCreationOptions,
    SessionManager,
    ToolSettings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new session",
)
async def create_session(
    request: CreateSessionRequest,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    prompt_service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SessionResponse:
    """Create a new chat session.

    The model will be validated against available Ollama models.
    Optionally accepts a system prompt and tool/agent settings.

    Args:
        request: Session creation parameters
        session_manager: Injected SessionManager
        prompt_service: Injected SystemPromptService

    Returns:
        Created session metadata

    Raises:
        HTTPException: 400 if model doesn't exist
        HTTPException: 502 if Ollama communication fails
    """
    try:
        # Convert request to session creation options
        tool_settings = None
        if request.tool_settings:
            tool_settings = ToolSettings(
                tools=request.tool_settings.tools,
                tool_group=request.tool_settings.tool_group,
                execution_policy=request.tool_settings.execution_policy,
            )

        agent_settings = None
        if request.agent_settings:
            agent_settings = AgentSettings(
                enabled_agents=request.agent_settings.enabled_agents
            )

        # Load system prompt from file if source_file is provided but content is not
        system_prompt = request.system_prompt
        system_prompt_source_file = request.system_prompt_source_file

        if not system_prompt and system_prompt_source_file:
            try:
                system_prompt = prompt_service.get_prompt(system_prompt_source_file)
                logger.info(
                    f"Loaded system prompt from file: {system_prompt_source_file}"
                )
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"System prompt file '{system_prompt_source_file}' not found",
                )
            except Exception as e:
                logger.error(
                    f"Failed to load system prompt file '{system_prompt_source_file}': {e}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to load system prompt file: {str(e)}",
                )

        options = SessionCreationOptions(
            model=request.model,
            system_prompt=system_prompt,
            system_prompt_source_file=system_prompt_source_file,
            tool_settings=tool_settings,
            agent_settings=agent_settings,
        )

        # Create the session
        session = await session_manager.create_session(options)

        # Convert to response
        return SessionResponse(
            session_id=session.session_id,
            model=session.model,
            created_at=session.metadata.created_at,
            updated_at=session.metadata.updated_at,
            message_count=session.metadata.message_count,
            tool_settings=ToolSettingsResponse(
                tools=session.metadata.tool_settings.tools,
                tool_group=session.metadata.tool_settings.tool_group,
                execution_policy=session.metadata.tool_settings.execution_policy,
            ),
            agent_settings=AgentSettingsResponse(
                enabled_agents=session.metadata.agent_settings.enabled_agents
            ),
        )

    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except ValueError as e:
        # Model not found or validation error
        logger.warning(f"Session creation failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Ollama communication error or other unexpected error
        logger.error(f"Failed to create session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create session: {str(e)}",
        )


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List all sessions",
)
async def list_sessions(
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> SessionListResponse:
    """List all chat sessions, sorted by most recently updated.

    Returns session metadata including summaries and previews.

    Args:
        session_manager: Injected SessionManager

    Returns:
        List of session summaries
    """
    try:
        sessions = session_manager.list_sessions()

        # Convert to response format
        items = []
        for session in sessions:
            summary = None
            if session.metadata.summary:
                summary = SummaryResponse(
                    summary=session.metadata.summary.summary,
                    topics=session.metadata.summary.topics,
                )

            items.append(
                SessionListItem(
                    session_id=session.session_id,
                    model=session.model,
                    created_at=session.metadata.created_at,
                    updated_at=session.metadata.updated_at,
                    message_count=session.metadata.message_count,
                    summary=summary,
                    preview=session.get_preview(),
                )
            )

        return SessionListResponse(sessions=items)

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}",
        )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session details",
)
async def get_session(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> SessionDetailResponse:
    """Get full details of a specific session including message history.

    Args:
        session_id: The session ID to retrieve
        session_manager: Injected SessionManager

    Returns:
        Session details with full message history

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        session = session_manager.get_session(session_id)

        # Convert messages to response format
        messages = []
        for msg in session.messages:
            msg_dict = asdict(msg)
            messages.append(MessageResponse(**msg_dict))

        return SessionDetailResponse(
            session_id=session.session_id,
            model=session.model,
            created_at=session.metadata.created_at,
            updated_at=session.metadata.updated_at,
            message_count=session.metadata.message_count,
            tool_settings=ToolSettingsResponse(
                tools=session.metadata.tool_settings.tools,
                tool_group=session.metadata.tool_settings.tool_group,
                execution_policy=session.metadata.tool_settings.execution_policy,
            ),
            agent_settings=AgentSettingsResponse(
                enabled_agents=session.metadata.agent_settings.enabled_agents
            ),
            messages=messages,
        )

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}",
        )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
)
async def delete_session(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> None:
    """Delete a chat session permanently.

    Args:
        session_id: The session ID to delete
        session_manager: Injected SessionManager

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        session_manager.delete_session(session_id)
        logger.info(f"Deleted session {session_id}")

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}",
        )


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update session metadata",
)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> SessionResponse:
    """Update session metadata (model, tool settings, agent settings).

    Args:
        session_id: The session ID to update
        request: Updated session parameters
        session_manager: Injected SessionManager

    Returns:
        Updated session metadata

    Raises:
        HTTPException: 404 if session not found
        HTTPException: 400 if new model doesn't exist
    """
    try:
        # Convert request to domain types
        tool_settings = None
        if request.tool_settings:
            tool_settings = ToolSettings(
                tools=request.tool_settings.tools,
                tool_group=request.tool_settings.tool_group,
                execution_policy=request.tool_settings.execution_policy,
            )

        agent_settings = None
        if request.agent_settings:
            agent_settings = AgentSettings(
                enabled_agents=request.agent_settings.enabled_agents
            )

        # Update the session
        session = await session_manager.update_session(
            session_id=session_id,
            model=request.model,
            tool_settings=tool_settings,
            agent_settings=agent_settings,
        )

        # Convert to response
        return SessionResponse(
            session_id=session.session_id,
            model=session.model,
            created_at=session.metadata.created_at,
            updated_at=session.metadata.updated_at,
            message_count=session.metadata.message_count,
            tool_settings=ToolSettingsResponse(
                tools=session.metadata.tool_settings.tools,
                tool_group=session.metadata.tool_settings.tool_group,
                execution_policy=session.metadata.tool_settings.execution_policy,
            ),
            agent_settings=AgentSettingsResponse(
                enabled_agents=session.metadata.agent_settings.enabled_agents
            ),
        )

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except ValueError as e:
        # Model not found or validation error
        logger.warning(f"Session update failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}",
        )


@router.get(
    "/{session_id}/messages",
    response_model=MessagesResponse,
    summary="Get session messages",
)
async def get_messages(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> MessagesResponse:
    """Get all messages from a session.

    Args:
        session_id: The session ID
        session_manager: Injected SessionManager

    Returns:
        List of messages in the session

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        messages = session_manager.get_messages(session_id)

        # Convert to response format
        message_responses = []
        for msg in messages:
            msg_dict = asdict(msg)
            message_responses.append(MessageResponse(**msg_dict))

        return MessagesResponse(messages=message_responses)

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as e:
        logger.error(
            f"Failed to get messages for session {session_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}",
        )


@router.put(
    "/{session_id}/messages/{message_index}",
    status_code=status.HTTP_200_OK,
    summary="Edit a message and truncate subsequent messages",
)
async def edit_message(
    session_id: str,
    message_index: int,
    request: EditMessageRequest,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> None:
    """Edit a message in the session and remove all messages after it.

    This allows users to branch the conversation from any point by editing
    a previous message. All messages after the edited message are removed.

    Only user messages can be edited.

    Args:
        session_id: The session ID
        message_index: The index of the message to edit (0-based)
        request: New message content
        session_manager: Injected SessionManager

    Raises:
        HTTPException: 404 if session not found
        HTTPException: 400 if message_index is out of range or not a user message
    """
    try:
        session = session_manager.get_session(session_id)

        # Validate message index
        if message_index < 0 or message_index >= len(session.messages):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Message index {message_index} out of range (0-{len(session.messages) - 1})",
            )

        # Edit the message (this also truncates)
        try:
            session.edit_message(message_index, request.content)
        except ValueError as e:
            # Not a user message
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Save the session
        session.save(session_manager.sessions_dir)
        logger.info(
            f"Edited message {message_index} in session {session_id} and truncated subsequent messages"
        )

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Failed to edit message in session {session_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to edit message: {str(e)}",
        )


@router.put(
    "/{session_id}/system-prompt",
    status_code=status.HTTP_200_OK,
    summary="Set or update session system prompt",
)
async def set_session_system_prompt(
    session_id: str,
    request: SetSessionSystemPromptRequest,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> None:
    """Set or update the system prompt for a session.

    If a system prompt already exists, it will be replaced at index 0.
    If no system prompt exists, a new one will be added at index 0.

    Note: This does NOT truncate the conversation history.

    Args:
        session_id: The session ID
        request: System prompt content and optional source file
        session_manager: Injected SessionManager

    Raises:
        HTTPException: 404 if session not found
        HTTPException: 500 if operation fails
    """
    try:
        session = session_manager.get_session(session_id)
        session.set_system_prompt(request.content, request.source_file)
        session.save(session_manager.sessions_dir)
        logger.info(f"Set system prompt for session {session_id}")

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as e:
        logger.error(
            f"Failed to set system prompt for session {session_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set system prompt: {str(e)}",
        )


@router.delete(
    "/{session_id}/system-prompt",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove session system prompt",
)
async def remove_session_system_prompt(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> None:
    """Remove the system prompt from a session.

    If a system prompt exists at index 0, it will be deleted and
    subsequent messages will shift up.

    Args:
        session_id: The session ID
        session_manager: Injected SessionManager

    Raises:
        HTTPException: 404 if session not found
        HTTPException: 400 if no system prompt exists
        HTTPException: 500 if operation fails
    """
    try:
        session = session_manager.get_session(session_id)
        session.remove_system_prompt()
        session.save(session_manager.sessions_dir)
        logger.info(f"Removed system prompt from session {session_id}")

    except FileNotFoundError:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except ValueError as e:
        # No system prompt to remove
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to remove system prompt from session {session_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove system prompt: {str(e)}",
        )


@router.get(
    "/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Get session status",
)
async def get_session_status(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    context_window_service: Annotated[
        DynamicContextWindowService, Depends(get_context_window_service)
    ],
    system_prompt_service: Annotated[
        SystemPromptService, Depends(get_system_prompt_service)
    ],
) -> SessionStatusResponse:
    """Get full status information for a session.

    This endpoint provides comprehensive session state information including:
    - Basic session info (ID, model, message count)
    - Context window configuration and status
    - Tool settings and active tools
    - Agent settings and enabled agents
    - System prompt file (if any)
    - Conversation summary (if available)

    Args:
        session_id: The session ID
        session_manager: Injected SessionManager
        context_window_service: Injected DynamicContextWindowService
        system_prompt_service: Injected SystemPromptService

    Returns:
        SessionStatusResponse with full session status

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        session = session_manager.get_session(session_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Get model max context
    model_max_context = await context_window_service.get_model_max_context(
        session.model
    )

    # Get system prompt file (from first message if it's a system message)
    system_prompt_file: str | None = None
    if session.messages:
        first_msg = session.messages[0]
        if hasattr(first_msg, 'role') and first_msg.role == 'system':
            # Access source_file with type cast since we know it's a SystemMessage
            source_file = getattr(first_msg, 'source_file', None)
            if source_file is not None:
                system_prompt_file = str(source_file)

    # Build context window status with proper field mapping
    ctx_config = session.metadata.context_window_config
    context_window_status = ContextWindowStatus(
        dynamic_enabled=ctx_config.dynamic_enabled,
        current_window=ctx_config.current_window,
        model_max_context=model_max_context,
        last_adjustment_reason=ctx_config.last_adjustment,
        manual_override=ctx_config.manual_override,
    )

    # Build the status response
    from mochi_server.models.status import ConversationSummaryStatus
    
    response = SessionStatusResponse(
        session_id=session.session_id,
        model=session.model,
        message_count=session.metadata.message_count,
        context_window=context_window_status,
        tools_enabled=bool(session.metadata.tool_settings.tools or session.metadata.tool_settings.tool_group),
        active_tools=session.metadata.tool_settings.tools or [],
        execution_policy=session.metadata.tool_settings.execution_policy,
        agents_enabled=bool(session.metadata.agent_settings.enabled_agents),
        enabled_agents=session.metadata.agent_settings.enabled_agents,
        system_prompt_file=system_prompt_file,
        summary=ConversationSummaryStatus(**session.metadata.summary.__dict__) if session.metadata.summary else None,
        summary_model=session.metadata.summary_model,
    )

    return response
