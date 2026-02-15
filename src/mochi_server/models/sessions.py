"""Pydantic models for session API requests and responses."""

from pydantic import BaseModel, Field


class ToolSettingsRequest(BaseModel):
    """Tool settings for a session."""

    tools: list[str] = Field(
        default_factory=list, description="List of enabled tool names"
    )
    tool_group: str | None = Field(None, description="Tool group name to enable")
    execution_policy: str = Field(
        "always_confirm",
        description="Tool execution policy: always_confirm, never_confirm, or auto",
    )


class AgentSettingsRequest(BaseModel):
    """Agent settings for a session."""

    enabled_agents: list[str] = Field(
        default_factory=list,
        description="List of enabled agent names",
    )


class CreateSessionRequest(BaseModel):
    """Request body for creating a new session."""

    model: str = Field(..., description="The LLM model to use for this session")
    system_prompt: str | None = Field(
        None, description="Optional system prompt content"
    )
    system_prompt_source_file: str | None = Field(
        None,
        description="Optional filename of the system prompt (for reference)",
    )
    tool_settings: ToolSettingsRequest | None = Field(
        None,
        description="Optional tool configuration",
    )
    agent_settings: AgentSettingsRequest | None = Field(
        None,
        description="Optional agent configuration",
    )


class UpdateSessionRequest(BaseModel):
    """Request body for updating a session."""

    model: str | None = Field(None, description="New model to use for this session")
    tool_settings: ToolSettingsRequest | None = Field(
        None,
        description="New tool configuration",
    )
    agent_settings: AgentSettingsRequest | None = Field(
        None,
        description="New agent configuration",
    )


class EditMessageRequest(BaseModel):
    """Request body for editing a message."""

    content: str = Field(..., description="New content for the message")


class SummaryResponse(BaseModel):
    """Conversation summary information."""

    summary: str = Field("", description="Summary text")
    topics: list[str] = Field(
        default_factory=list, description="List of topics discussed"
    )


class ToolSettingsResponse(BaseModel):
    """Tool settings in a response."""

    tools: list[str]
    tool_group: str | None
    execution_policy: str


class AgentSettingsResponse(BaseModel):
    """Agent settings in a response."""

    enabled_agents: list[str]


class SessionResponse(BaseModel):
    """Response model for a single session (metadata only)."""

    session_id: str
    model: str
    created_at: str
    updated_at: str
    message_count: int
    tool_settings: ToolSettingsResponse
    agent_settings: AgentSettingsResponse


class SessionListItem(BaseModel):
    """A session item in the list response."""

    session_id: str
    model: str
    created_at: str
    updated_at: str
    message_count: int
    summary: SummaryResponse | None = None
    preview: str = Field("", description="Preview of first user message")


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""

    sessions: list[SessionListItem]


class MessageResponse(BaseModel):
    """Response model for a single message."""

    role: str
    content: str
    message_id: str | None = None
    timestamp: str | None = None
    model: str | None = None
    eval_count: int | None = None
    prompt_eval_count: int | None = None
    tool_calls: list[dict] | None = None
    source_file: str | None = None
    tool_name: str | None = None


class SessionDetailResponse(BaseModel):
    """Response model for a session with full message history."""

    session_id: str
    model: str
    created_at: str
    updated_at: str
    message_count: int
    tool_settings: ToolSettingsResponse
    agent_settings: AgentSettingsResponse
    messages: list[MessageResponse]


class MessagesResponse(BaseModel):
    """Response model for getting session messages."""

    messages: list[MessageResponse]
