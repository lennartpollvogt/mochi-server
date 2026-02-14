"""Configuration module for mochi-server using pydantic-settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MochiServerSettings(BaseSettings):
    """Main configuration settings for mochi-server.

    All settings can be overridden via environment variables with the MOCHI_ prefix.
    For example, MOCHI_OLLAMA_HOST will override the ollama_host setting.
    """

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Ollama
    ollama_host: str = "http://localhost:11434"

    # Data directories (relative to data_dir)
    data_dir: str = "."
    sessions_dir: str = "chat_sessions"
    tools_dir: str = "tools"
    agents_dir: str = "agents"
    agent_chats_dir: str = "agents/agent_chats"
    system_prompts_dir: str = "system_prompts"

    # Planning/execution prompt paths
    planning_prompt_path: str = "docs/agents/agent_prompt_planning.md"
    execution_prompt_path: str = "docs/agents/agent_prompt_execution.md"

    # Summarization
    summarization_enabled: bool = True

    # Context window
    dynamic_context_window_enabled: bool = True

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Logging
    log_level: str = "INFO"

    # Agent execution
    max_agent_iterations: int = 50

    model_config = SettingsConfigDict(env_prefix="MOCHI_")

    # --- Resolved paths (computed from data_dir + relative dirs) ---

    @property
    def resolved_sessions_dir(self) -> Path:
        """Get the full path to the sessions directory."""
        return Path(self.data_dir) / self.sessions_dir

    @property
    def resolved_tools_dir(self) -> Path:
        """Get the full path to the tools directory."""
        return Path(self.data_dir) / self.tools_dir

    @property
    def resolved_agents_dir(self) -> Path:
        """Get the full path to the agents directory."""
        return Path(self.data_dir) / self.agents_dir

    @property
    def resolved_agent_chats_dir(self) -> Path:
        """Get the full path to the agent chats directory."""
        return Path(self.data_dir) / self.agent_chats_dir

    @property
    def resolved_system_prompts_dir(self) -> Path:
        """Get the full path to the system prompts directory."""
        return Path(self.data_dir) / self.system_prompts_dir

    @property
    def resolved_planning_prompt_path(self) -> Path:
        """Get the full path to the planning prompt file."""
        return Path(self.data_dir) / self.planning_prompt_path

    @property
    def resolved_execution_prompt_path(self) -> Path:
        """Get the full path to the execution prompt file."""
        return Path(self.data_dir) / self.execution_prompt_path
