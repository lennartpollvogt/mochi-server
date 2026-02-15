"""System prompts router for managing prompt files.

This module provides REST API endpoints for:
- Listing all system prompt files
- Getting prompt file content
- Creating new prompt files
- Updating existing prompt files
- Deleting prompt files
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mochi_server.dependencies import get_system_prompt_service
from mochi_server.models.system_prompts import (
    CreateSystemPromptRequest,
    SystemPromptListItem,
    SystemPromptListResponse,
    SystemPromptResponse,
    UpdateSystemPromptRequest,
)
from mochi_server.services import SystemPromptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system-prompts", tags=["system-prompts"])


@router.get(
    "",
    response_model=SystemPromptListResponse,
    summary="List all system prompts",
)
async def list_system_prompts(
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptListResponse:
    """List all available system prompt files.

    Returns metadata for each .md file in the system_prompts_dir, including:
    - filename
    - preview (first 250 characters)
    - word_count

    Args:
        service: Injected SystemPromptService

    Returns:
        List of system prompt metadata
    """
    try:
        prompts_data = service.list_prompts()
        prompts = [
            SystemPromptListItem(
                filename=p["filename"],
                preview=p["preview"],
                word_count=p["word_count"],
            )
            for p in prompts_data
        ]
        return SystemPromptListResponse(prompts=prompts)
    except Exception as e:
        logger.error(f"Failed to list system prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list system prompts: {str(e)}",
        )


@router.get(
    "/{filename}",
    response_model=SystemPromptResponse,
    summary="Get a system prompt",
)
async def get_system_prompt(
    filename: str,
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptResponse:
    """Get the full content of a specific system prompt file.

    Args:
        filename: Name of the prompt file (e.g., 'helpful.md')
        service: Injected SystemPromptService

    Returns:
        Prompt file content

    Raises:
        HTTPException: 404 if file not found
        HTTPException: 400 if filename is invalid
        HTTPException: 500 if file cannot be read
    """
    try:
        content = service.get_prompt(filename)
        return SystemPromptResponse(filename=filename, content=content)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System prompt '{filename}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get system prompt '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read system prompt: {str(e)}",
        )


@router.post(
    "",
    response_model=SystemPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new system prompt",
)
async def create_system_prompt(
    request: CreateSystemPromptRequest,
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptResponse:
    """Create a new system prompt file.

    The filename must end with .md extension and the content must be
    non-empty and under 20,000 characters.

    Args:
        request: Prompt creation parameters
        service: Injected SystemPromptService

    Returns:
        Created prompt file content

    Raises:
        HTTPException: 400 if validation fails
        HTTPException: 409 if file already exists
        HTTPException: 500 if file cannot be written
    """
    try:
        service.create_prompt(request.filename, request.content)
        return SystemPromptResponse(filename=request.filename, content=request.content)
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"System prompt '{request.filename}' already exists",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create system prompt '{request.filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create system prompt: {str(e)}",
        )


@router.put(
    "/{filename}",
    response_model=SystemPromptResponse,
    summary="Update a system prompt",
)
async def update_system_prompt(
    filename: str,
    request: UpdateSystemPromptRequest,
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptResponse:
    """Update an existing system prompt file.

    The content must be non-empty and under 20,000 characters.

    Args:
        filename: Name of the prompt file to update
        request: New prompt content
        service: Injected SystemPromptService

    Returns:
        Updated prompt file content

    Raises:
        HTTPException: 404 if file not found
        HTTPException: 400 if validation fails
        HTTPException: 500 if file cannot be written
    """
    try:
        service.update_prompt(filename, request.content)
        return SystemPromptResponse(filename=filename, content=request.content)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System prompt '{filename}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update system prompt '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update system prompt: {str(e)}",
        )


@router.delete(
    "/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a system prompt",
)
async def delete_system_prompt(
    filename: str,
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> None:
    """Delete a system prompt file.

    Args:
        filename: Name of the prompt file to delete
        service: Injected SystemPromptService

    Raises:
        HTTPException: 404 if file not found
        HTTPException: 400 if filename is invalid
        HTTPException: 500 if file cannot be deleted
    """
    try:
        service.delete_prompt(filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System prompt '{filename}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to delete system prompt '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete system prompt: {str(e)}",
        )
