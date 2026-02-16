"""Pydantic models for system prompt API requests and responses."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SystemPromptListItem(BaseModel):
    """Metadata for a system prompt file in list responses."""

    filename: str = Field(
        ..., description="Name of the prompt file (e.g., 'helpful.md')"
    )
    preview: str = Field(..., description="First 250 characters of the prompt")
    word_count: int = Field(..., description="Total word count in the prompt")

    model_config = ConfigDict(from_attributes=True)


class SystemPromptListResponse(BaseModel):
    """Response model for listing all system prompts."""

    prompts: list[SystemPromptListItem] = Field(
        default_factory=list,
        description="List of available system prompt files",
    )

    model_config = ConfigDict(from_attributes=True)


class SystemPromptResponse(BaseModel):
    """Response model for a single system prompt file."""

    filename: str = Field(..., description="Name of the prompt file")
    content: str = Field(..., description="Full content of the prompt")

    model_config = ConfigDict(from_attributes=True)


class CreateSystemPromptRequest(BaseModel):
    """Request model for creating a new system prompt file."""

    filename: str = Field(
        ...,
        description="Name of the prompt file (must end with .md)",
        min_length=4,
    )
    content: str = Field(
        ...,
        description="Content of the system prompt",
        min_length=1,
        max_length=20000,
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate that filename ends with .md extension."""
        if not v.endswith(".md"):
            raise ValueError("Filename must end with .md extension")
        if "/" in v or "\\" in v:
            raise ValueError("Filename cannot contain path separators")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate that content is not just whitespace."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        return v

    model_config = ConfigDict(from_attributes=True)


class UpdateSystemPromptRequest(BaseModel):
    """Request model for updating an existing system prompt file."""

    content: str = Field(
        ...,
        description="New content for the system prompt",
        min_length=1,
        max_length=20000,
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate that content is not just whitespace."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        return v

    model_config = ConfigDict(from_attributes=True)


class SetSessionSystemPromptRequest(BaseModel):
    """Request model for setting a system prompt on a session."""

    content: str = Field(
        ...,
        description="Content of the system prompt to set",
        min_length=1,
        max_length=20000,
    )
    source_file: str | None = Field(
        None,
        description="Optional filename reference for tracking prompt source",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate that content is not just whitespace."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        return v

    model_config = ConfigDict(from_attributes=True)
