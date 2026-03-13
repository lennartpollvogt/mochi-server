"""Filesystem and terminal tools for Mochi Server.

This module exposes a small set of file-management and shell-execution tools
that follow Mochi Server's discovery model:

- each exported tool is a plain Python function
- every parameter has type hints
- every function has a docstring
- every function returns a string for LLM consumption

These tools operate relative to the current working directory, which in a
typical Mochi Server setup is the configured data directory.

Security note:
These tools intentionally provide powerful local filesystem and shell access.
They should only be enabled for trusted sessions and should generally be used
with an execution policy that requires user confirmation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

__all__ = [
    "create_directory",
    "delete_path",
    "edit_file",
    "list_directory",
    "read_file",
    "terminal",
]


def _resolve_path(path: str) -> Path:
    """Resolve a user-provided path relative to the current working directory.

    Args:
        path: A relative or absolute filesystem path.

    Returns:
        Path: The normalized absolute path.

    Raises:
        ValueError: If the path is empty.
    """
    cleaned = path.strip()
    if not cleaned:
        raise ValueError("Path must not be empty")

    return Path(cleaned).expanduser().resolve()


def _format_path(path: Path) -> str:
    """Format a path for human-readable tool responses.

    Args:
        path: The path to format.

    Returns:
        str: The string form of the path.
    """
    return str(path)


def create_directory(path: str) -> str:
    """
    Create a directory and any missing parent directories.

    Use this when you need to create a new folder on disk.

    Args:
        path (str): The directory path to create.

    Returns:
        str: A success message including the created directory path, or an error message.
    """
    try:
        target = _resolve_path(path)
        target.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {_format_path(target)}"
    except Exception as exc:
        return f"Error: Failed to create directory '{path}': {exc}"


def delete_path(path: str) -> str:
    """
    Delete a file or directory from disk.

    If the target is a directory, it is deleted recursively together with all
    of its contents. Use this carefully.

    Args:
        path (str): The file or directory path to delete.

    Returns:
        str: A success message, or an error message if deletion fails.
    """
    try:
        target = _resolve_path(path)

        if not target.exists():
            return f"Error: Path does not exist: {_format_path(target)}"

        if target.is_dir():
            shutil.rmtree(target)
            return f"Deleted directory: {_format_path(target)}"

        target.unlink()
        return f"Deleted file: {_format_path(target)}"
    except Exception as exc:
        return f"Error: Failed to delete '{path}': {exc}"


def edit_file(
    path: str,
    content: str,
    mode: str = "overwrite",
    create_parents: bool = True,
) -> str:
    """
    Create or modify a text file.

    Supported modes:
    - "overwrite": replace the file content entirely
    - "append": append content to the end of the file
    - "prepend": insert content at the beginning of the file

    Args:
        path (str): The file path to write to.
        content (str): The text content to write.
        mode (str): The write mode: "overwrite", "append", or "prepend".
        create_parents (bool): Whether to create missing parent directories.

    Returns:
        str: A success message describing what changed, or an error message.
    """
    try:
        target = _resolve_path(path)

        if create_parents:
            target.parent.mkdir(parents=True, exist_ok=True)

        normalized_mode = mode.strip().lower()

        if normalized_mode == "overwrite":
            target.write_text(content, encoding="utf-8")
            return f"Wrote file: {_format_path(target)}"

        if normalized_mode == "append":
            with target.open("a", encoding="utf-8") as file_handle:
                file_handle.write(content)
            return f"Appended to file: {_format_path(target)}"

        if normalized_mode == "prepend":
            existing = ""
            if target.exists():
                existing = target.read_text(encoding="utf-8")
            target.write_text(content + existing, encoding="utf-8")
            return f"Prepended to file: {_format_path(target)}"

        return (
            "Error: Invalid mode. Supported modes are "
            "'overwrite', 'append', and 'prepend'."
        )
    except Exception as exc:
        return f"Error: Failed to edit file '{path}': {exc}"


def list_directory(path: str = ".") -> str:
    """
    List the contents of a directory.

    Entries are returned one per line and prefixed with "[DIR]" or "[FILE]".

    Args:
        path (str): The directory path to inspect. Defaults to the current directory.

    Returns:
        str: A directory listing, or an error message.
    """
    try:
        target = _resolve_path(path)

        if not target.exists():
            return f"Error: Path does not exist: {_format_path(target)}"

        if not target.is_dir():
            return f"Error: Path is not a directory: {_format_path(target)}"

        entries = sorted(
            target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        )

        if not entries:
            return f"Directory is empty: {_format_path(target)}"

        lines = [f"Contents of {_format_path(target)}:"]
        for entry in entries:
            kind = "[DIR]" if entry.is_dir() else "[FILE]"
            lines.append(f"{kind} {entry.name}")

        return "\n".join(lines)
    except Exception as exc:
        return f"Error: Failed to list directory '{path}': {exc}"


def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
    """
    Read text from a file, optionally limited to a line range.

    If end_line is 0 or smaller than start_line, the tool reads from start_line
    through the end of the file.

    Args:
        path (str): The file path to read.
        start_line (int): The 1-based line number to start reading from.
        end_line (int): The inclusive 1-based line number to stop at. Use 0 for EOF.

    Returns:
        str: The requested file contents, or an error message.
    """
    try:
        target = _resolve_path(path)

        if not target.exists():
            return f"Error: File does not exist: {_format_path(target)}"

        if not target.is_file():
            return f"Error: Path is not a file: {_format_path(target)}"

        if start_line < 1:
            return "Error: start_line must be at least 1"

        text = target.read_text(encoding="utf-8")
        lines = text.splitlines()

        if not lines:
            return f"File is empty: {_format_path(target)}"

        start_index = start_line - 1

        if start_index >= len(lines):
            return (
                f"Error: start_line {start_line} is beyond the end of the file "
                f"({len(lines)} lines)"
            )

        if end_line > 0 and end_line < start_line:
            end_index = len(lines)
        elif end_line > 0:
            end_index = min(end_line, len(lines))
        else:
            end_index = len(lines)

        selected = lines[start_index:end_index]
        header = f"File: {_format_path(target)} (lines {start_line}-{start_index + len(selected)})"
        return header + "\n" + "\n".join(selected)
    except Exception as exc:
        return f"Error: Failed to read file '{path}': {exc}"


def terminal(
    command: str,
    working_directory: str = ".",
    timeout_seconds: int = 30,
) -> str:
    """
    Execute a shell command and return its combined output.

    The command runs in the provided working directory. Standard output and
    standard error are combined into a single string.

    Args:
        command (str): The shell command to execute.
        working_directory (str): The directory in which to run the command.
        timeout_seconds (int): Maximum allowed runtime in seconds.

    Returns:
        str: The command output and exit status, or an error message.
    """
    try:
        if not command.strip():
            return "Error: Command must not be empty"

        cwd = _resolve_path(working_directory)

        if not cwd.exists():
            return f"Error: Working directory does not exist: {_format_path(cwd)}"

        if not cwd.is_dir():
            return f"Error: Working directory is not a directory: {_format_path(cwd)}"

        if timeout_seconds < 1:
            return "Error: timeout_seconds must be at least 1"

        completed = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )

        output_parts = []
        if completed.stdout:
            output_parts.append("STDOUT:\n" + completed.stdout.rstrip())
        if completed.stderr:
            output_parts.append("STDERR:\n" + completed.stderr.rstrip())

        output = "\n\n".join(output_parts).strip()
        if not output:
            output = "(no output)"

        return (
            f"Command: {command}\n"
            f"Working directory: {_format_path(cwd)}\n"
            f"Exit code: {completed.returncode}\n"
            f"{output}"
        )
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout_seconds} seconds: {command}"
    except Exception as exc:
        return f"Error: Failed to execute command '{command}': {exc}"
