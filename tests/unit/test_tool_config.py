"""Unit tests for tool configuration and execution policy."""

from dataclasses import dataclass, field

from mochi_server.tools.config import (
    ToolExecutionPolicy,
    normalize_execution_policy,
    requires_confirmation,
    resolve_tool_execution_policy,
    tool_requires_confirmation,
)


@dataclass
class DummyToolSettings:
    """Simple test double for session tool settings."""

    execution_policy: str = "always_confirm"
    tool_policies: dict[str, str] = field(default_factory=dict)


class TestToolExecutionPolicy:
    """Tests for the ToolExecutionPolicy enum."""

    def test_policy_always_confirm(self):
        """Verify always_confirm value is correct."""
        assert ToolExecutionPolicy.ALWAYS_CONFIRM.value == "always_confirm"

    def test_policy_never_confirm(self):
        """Verify never_confirm value is correct."""
        assert ToolExecutionPolicy.NEVER_CONFIRM.value == "never_confirm"


class TestNormalizeExecutionPolicy:
    """Tests for normalize_execution_policy."""

    def test_normalize_enum(self):
        """Verify enum values are returned unchanged."""
        assert (
            normalize_execution_policy(ToolExecutionPolicy.ALWAYS_CONFIRM)
            == ToolExecutionPolicy.ALWAYS_CONFIRM
        )

    def test_normalize_valid_string(self):
        """Verify valid string values are converted to enum values."""
        assert (
            normalize_execution_policy("never_confirm")
            == ToolExecutionPolicy.NEVER_CONFIRM
        )

    def test_normalize_invalid_string(self):
        """Verify invalid strings return None."""
        assert normalize_execution_policy("auto") is None

    def test_normalize_none(self):
        """Verify None returns None."""
        assert normalize_execution_policy(None) is None


class TestRequiresConfirmation:
    """Tests for the requires_confirmation function."""

    def test_requires_confirmation_always_confirm_with_enum(self):
        """Verify True for always_confirm enum."""
        assert requires_confirmation(ToolExecutionPolicy.ALWAYS_CONFIRM) is True

    def test_requires_confirmation_never_confirm_with_enum(self):
        """Verify False for never_confirm enum."""
        assert requires_confirmation(ToolExecutionPolicy.NEVER_CONFIRM) is False

    def test_requires_confirmation_always_confirm_with_string(self):
        """Verify True for always_confirm string."""
        assert requires_confirmation("always_confirm") is True

    def test_requires_confirmation_never_confirm_with_string(self):
        """Verify False for never_confirm string."""
        assert requires_confirmation("never_confirm") is False

    def test_requires_confirmation_invalid_policy(self):
        """Verify True for unknown policy (safe default)."""
        assert requires_confirmation("invalid_policy") is True

    def test_requires_confirmation_empty_string(self):
        """Verify True for empty string (safe default)."""
        assert requires_confirmation("") is True

    def test_requires_confirmation_none(self):
        """Verify True for None (safe default)."""
        assert requires_confirmation(None) is True


class TestResolveToolExecutionPolicy:
    """Tests for resolve_tool_execution_policy."""

    def test_uses_per_tool_override_first(self):
        """Verify per-tool override takes precedence over default policy."""
        settings = DummyToolSettings(
            execution_policy="always_confirm",
            tool_policies={"safe_tool": "never_confirm"},
        )

        resolved = resolve_tool_execution_policy("safe_tool", settings)

        assert resolved == ToolExecutionPolicy.NEVER_CONFIRM

    def test_falls_back_to_default_policy(self):
        """Verify default session policy is used when no override exists."""
        settings = DummyToolSettings(
            execution_policy="never_confirm",
            tool_policies={},
        )

        resolved = resolve_tool_execution_policy("some_tool", settings)

        assert resolved == ToolExecutionPolicy.NEVER_CONFIRM

    def test_invalid_override_falls_back_to_default(self):
        """Verify invalid per-tool override falls back to default policy."""
        settings = DummyToolSettings(
            execution_policy="never_confirm",
            tool_policies={"some_tool": "invalid_policy"},
        )

        resolved = resolve_tool_execution_policy("some_tool", settings)

        assert resolved == ToolExecutionPolicy.NEVER_CONFIRM

    def test_invalid_default_falls_back_to_always_confirm(self):
        """Verify invalid default policy falls back to safe always_confirm."""
        settings = DummyToolSettings(
            execution_policy="invalid_policy",
            tool_policies={},
        )

        resolved = resolve_tool_execution_policy("some_tool", settings)

        assert resolved == ToolExecutionPolicy.ALWAYS_CONFIRM


class TestToolRequiresConfirmation:
    """Tests for tool_requires_confirmation."""

    def test_tool_requires_confirmation_from_default_policy(self):
        """Verify tool confirmation is derived from default session policy."""
        settings = DummyToolSettings(
            execution_policy="always_confirm",
            tool_policies={},
        )

        assert tool_requires_confirmation("some_tool", settings) is True

    def test_tool_requires_confirmation_from_override(self):
        """Verify per-tool override can disable confirmation."""
        settings = DummyToolSettings(
            execution_policy="always_confirm",
            tool_policies={"safe_tool": "never_confirm"},
        )

        assert tool_requires_confirmation("safe_tool", settings) is False

    def test_tool_requires_confirmation_unknown_policy_is_safe(self):
        """Verify invalid settings default to requiring confirmation."""
        settings = DummyToolSettings(
            execution_policy="invalid_policy",
            tool_policies={},
        )

        assert tool_requires_confirmation("some_tool", settings) is True
