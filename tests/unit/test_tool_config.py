"""Unit tests for tool configuration and execution policy."""


from mochi_server.tools.config import (
    ToolExecutionPolicy,
    requires_confirmation,
)


class TestToolExecutionPolicy:
    """Tests for the ToolExecutionPolicy enum."""

    def test_policy_always_confirm(self):
        """Verify always_confirm value is correct."""
        assert ToolExecutionPolicy.ALWAYS_CONFIRM.value == "always_confirm"

    def test_policy_never_confirm(self):
        """Verify never_confirm value is correct."""
        assert ToolExecutionPolicy.NEVER_CONFIRM.value == "never_confirm"

    def test_policy_auto(self):
        """Verify auto value is correct."""
        assert ToolExecutionPolicy.AUTO.value == "auto"


class TestRequiresConfirmation:
    """Tests for the requires_confirmation function."""

    def test_requires_confirmation_always_confirm_with_enum(self):
        """Verify True for always_confirm enum."""
        assert requires_confirmation(ToolExecutionPolicy.ALWAYS_CONFIRM) is True

    def test_requires_confirmation_never_confirm_with_enum(self):
        """Verify False for never_confirm enum."""
        assert requires_confirmation(ToolExecutionPolicy.NEVER_CONFIRM) is False

    def test_requires_confirmation_auto_with_enum(self):
        """Verify False for auto enum (model decides, so we auto-execute)."""
        assert requires_confirmation(ToolExecutionPolicy.AUTO) is False

    def test_requires_confirmation_always_confirm_with_string(self):
        """Verify True for always_confirm string."""
        assert requires_confirmation("always_confirm") is True

    def test_requires_confirmation_never_confirm_with_string(self):
        """Verify False for never_confirm string."""
        assert requires_confirmation("never_confirm") is False

    def test_requires_confirmation_auto_with_string(self):
        """Verify False for auto string."""
        assert requires_confirmation("auto") is False

    def test_requires_confirmation_invalid_policy(self):
        """Verify True for unknown policy (safe default)."""
        assert requires_confirmation("invalid_policy") is True

    def test_requires_confirmation_empty_string(self):
        """Verify True for empty string (safe default)."""
        assert requires_confirmation("") is True

    def test_requires_confirmation_none(self):
        """Verify True for None (safe default)."""
        assert requires_confirmation(None) is True
