"""System prompt management service.

This module provides the SystemPromptService class for managing system prompt
files stored as .md files in the configured system_prompts_dir.
"""

import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class PromptMetadata(TypedDict):
    """Metadata for a system prompt file."""

    filename: str
    preview: str
    word_count: int


class SystemPromptService:
    """Service for managing system prompt files on disk.

    This service handles CRUD operations for system prompt markdown files,
    including listing prompts with metadata, reading/writing files, and
    validation.
    """

    def __init__(self, prompts_dir: Path):
        """Initialize the SystemPromptService.

        Args:
            prompts_dir: Path to the directory containing system prompt files.
                        Will be created if it doesn't exist.
        """
        self.prompts_dir = prompts_dir
        self._ensure_directory_exists()

    def _ensure_directory_exists(self) -> None:
        """Create the prompts directory if it doesn't exist."""
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"System prompts directory ready: {self.prompts_dir}")

    def list_prompts(self) -> list[PromptMetadata]:
        """List all system prompt files with metadata.

        Scans the prompts directory for .md files and returns metadata
        including filename, preview (first 250 chars), and word count.

        Returns:
            List of dictionaries with keys: filename, preview, word_count
        """
        prompts = []

        if not self.prompts_dir.exists():
            return prompts

        for file_path in sorted(self.prompts_dir.glob("*.md")):
            try:
                content = self._read_file(file_path)
                preview = self._generate_preview(content, max_length=250)
                word_count = self._count_words(content)

                prompts.append(
                    PromptMetadata(
                        filename=file_path.name,
                        preview=preview,
                        word_count=word_count,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to read prompt file {file_path.name}: {e}")
                continue

        return prompts

    def get_prompt(self, filename: str) -> str:
        """Get the full content of a system prompt file.

        Args:
            filename: Name of the prompt file (e.g., 'helpful.md')

        Returns:
            Full content of the prompt file

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
            ValueError: If filename is invalid or file cannot be read
        """
        self._validate_filename(filename)
        file_path = self.prompts_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"System prompt '{filename}' not found")

        if not file_path.is_file():
            raise ValueError(f"'{filename}' is not a file")

        return self._read_file(file_path)

    def create_prompt(self, filename: str, content: str) -> None:
        """Create a new system prompt file.

        Args:
            filename: Name of the prompt file (must end with .md)
            content: Content of the system prompt

        Raises:
            ValueError: If filename is invalid or content fails validation
            FileExistsError: If a prompt with this filename already exists
        """
        self._validate_filename(filename)
        self._validate_content(content)

        file_path = self.prompts_dir / filename

        if file_path.exists():
            raise FileExistsError(f"System prompt '{filename}' already exists")

        self._write_file(file_path, content)
        logger.info(f"Created system prompt: {filename}")

    def update_prompt(self, filename: str, content: str) -> None:
        """Update an existing system prompt file.

        Args:
            filename: Name of the prompt file to update
            content: New content for the prompt

        Raises:
            ValueError: If filename is invalid or content fails validation
            FileNotFoundError: If the prompt file doesn't exist
        """
        self._validate_filename(filename)
        self._validate_content(content)

        file_path = self.prompts_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"System prompt '{filename}' not found")

        self._write_file(file_path, content)
        logger.info(f"Updated system prompt: {filename}")

    def delete_prompt(self, filename: str) -> None:
        """Delete a system prompt file.

        Args:
            filename: Name of the prompt file to delete

        Raises:
            ValueError: If filename is invalid
            FileNotFoundError: If the prompt file doesn't exist
        """
        self._validate_filename(filename)
        file_path = self.prompts_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"System prompt '{filename}' not found")

        file_path.unlink()
        logger.info(f"Deleted system prompt: {filename}")

    def _validate_filename(self, filename: str) -> None:
        """Validate that a filename is safe and has .md extension.

        Args:
            filename: The filename to validate

        Raises:
            ValueError: If filename is invalid
        """
        if not filename:
            raise ValueError("Filename cannot be empty")

        if not filename.endswith(".md"):
            raise ValueError("Filename must end with .md extension")

        if "/" in filename or "\\" in filename:
            raise ValueError("Filename cannot contain path separators")

        if filename.startswith("."):
            raise ValueError("Filename cannot start with a dot")

    def _validate_content(self, content: str) -> None:
        """Validate system prompt content.

        Args:
            content: The content to validate

        Raises:
            ValueError: If content is invalid
        """
        if not content.strip():
            raise ValueError("Content cannot be empty or whitespace only")

        if len(content) > 20000:
            raise ValueError("Content exceeds maximum length of 20,000 characters")

    def _read_file(self, file_path: Path) -> str:
        """Read a file with UTF-8 encoding and error handling.

        Args:
            file_path: Path to the file to read

        Returns:
            Content of the file

        Raises:
            ValueError: If file cannot be read or decoded
        """
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"File is not valid UTF-8: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read file: {e}")

    def _write_file(self, file_path: Path, content: str) -> None:
        """Write content to a file with UTF-8 encoding.

        Args:
            file_path: Path to the file to write
            content: Content to write

        Raises:
            ValueError: If file cannot be written
        """
        try:
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Failed to write file: {e}")

    def _generate_preview(self, content: str, max_length: int = 250) -> str:
        """Generate a preview of prompt content.

        Args:
            content: Full content to preview
            max_length: Maximum length of the preview

        Returns:
            Preview string, truncated with '...' if necessary
        """
        if len(content) <= max_length:
            return content

        # Truncate and add ellipsis
        return content[: max_length - 3].rstrip() + "..."

    def _count_words(self, content: str) -> int:
        """Count words in content using simple whitespace splitting.

        Args:
            content: The content to count words in

        Returns:
            Number of words
        """
        return len(content.split())
