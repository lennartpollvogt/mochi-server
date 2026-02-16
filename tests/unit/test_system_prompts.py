"""Unit tests for SystemPromptService."""

import pytest

from mochi_server.services import SystemPromptService


def test_list_prompts_empty_directory(tmp_path):
    """Test listing prompts when directory is empty."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")
    prompts = service.list_prompts()
    assert prompts == []


def test_list_prompts_with_files(tmp_path):
    """Test listing prompts with multiple .md files."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create test files
    (prompts_dir / "helpful.md").write_text(
        "You are a helpful assistant.", encoding="utf-8"
    )
    (prompts_dir / "coder.md").write_text(
        "You are an expert programmer. " * 50, encoding="utf-8"
    )
    (prompts_dir / "not_markdown.txt").write_text(
        "This should be ignored", encoding="utf-8"
    )

    service = SystemPromptService(prompts_dir=prompts_dir)
    prompts = service.list_prompts()

    assert len(prompts) == 2
    assert prompts[0]["filename"] == "coder.md"
    assert prompts[1]["filename"] == "helpful.md"
    assert prompts[1]["preview"] == "You are a helpful assistant."
    assert prompts[1]["word_count"] == 5


def test_list_prompts_long_content(tmp_path):
    """Test that preview is truncated to 250 characters."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    long_content = "A" * 300
    (prompts_dir / "long.md").write_text(long_content, encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)
    prompts = service.list_prompts()

    assert len(prompts) == 1
    preview = prompts[0]["preview"]
    assert isinstance(preview, str)
    assert len(preview) == 250
    assert preview.endswith("...")


def test_get_prompt_success(tmp_path):
    """Test getting a prompt file's content."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    content = "You are a helpful assistant."
    (prompts_dir / "helpful.md").write_text(content, encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)
    result = service.get_prompt("helpful.md")

    assert result == content


def test_get_prompt_not_found(tmp_path):
    """Test getting a non-existent prompt."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(FileNotFoundError, match="not found"):
        service.get_prompt("nonexistent.md")


def test_get_prompt_invalid_filename(tmp_path):
    """Test getting a prompt with invalid filename."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(ValueError, match="must end with .md"):
        service.get_prompt("invalid.txt")


def test_create_prompt_success(tmp_path):
    """Test creating a new prompt file."""
    prompts_dir = tmp_path / "prompts"
    service = SystemPromptService(prompts_dir=prompts_dir)

    content = "You are a helpful assistant."
    service.create_prompt("helpful.md", content)

    # Verify file was created
    file_path = prompts_dir / "helpful.md"
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == content


def test_create_prompt_already_exists(tmp_path):
    """Test creating a prompt that already exists."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "existing.md").write_text("Content", encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)

    with pytest.raises(FileExistsError, match="already exists"):
        service.create_prompt("existing.md", "New content")


def test_create_prompt_invalid_filename(tmp_path):
    """Test creating a prompt with invalid filename."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(ValueError, match="must end with .md"):
        service.create_prompt("invalid.txt", "Content")


def test_create_prompt_empty_content(tmp_path):
    """Test creating a prompt with empty content."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(ValueError, match="cannot be empty"):
        service.create_prompt("empty.md", "")


def test_create_prompt_whitespace_only(tmp_path):
    """Test creating a prompt with whitespace-only content."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(ValueError, match="cannot be empty"):
        service.create_prompt("whitespace.md", "   \n\t  ")


def test_create_prompt_too_long(tmp_path):
    """Test creating a prompt that exceeds max length."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    content = "A" * 20001
    with pytest.raises(ValueError, match="exceeds maximum length"):
        service.create_prompt("toolong.md", content)


def test_update_prompt_success(tmp_path):
    """Test updating an existing prompt."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "existing.md").write_text("Old content", encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)
    new_content = "New content"
    service.update_prompt("existing.md", new_content)

    # Verify file was updated
    assert (prompts_dir / "existing.md").read_text(encoding="utf-8") == new_content


def test_update_prompt_not_found(tmp_path):
    """Test updating a non-existent prompt."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(FileNotFoundError, match="not found"):
        service.update_prompt("nonexistent.md", "New content")


def test_update_prompt_invalid_content(tmp_path):
    """Test updating a prompt with invalid content."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "existing.md").write_text("Content", encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)

    with pytest.raises(ValueError, match="cannot be empty"):
        service.update_prompt("existing.md", "")


def test_delete_prompt_success(tmp_path):
    """Test deleting a prompt file."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    file_path = prompts_dir / "todelete.md"
    file_path.write_text("Content", encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)
    service.delete_prompt("todelete.md")

    # Verify file was deleted
    assert not file_path.exists()


def test_delete_prompt_not_found(tmp_path):
    """Test deleting a non-existent prompt."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(FileNotFoundError, match="not found"):
        service.delete_prompt("nonexistent.md")


def test_validate_filename_path_separators(tmp_path):
    """Test that filenames with path separators are rejected."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(ValueError, match="cannot contain path separators"):
        service._validate_filename("../evil.md")

    with pytest.raises(ValueError, match="cannot contain path separators"):
        service._validate_filename("subdir/file.md")


def test_validate_filename_hidden_file(tmp_path):
    """Test that hidden files (starting with dot) are rejected."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    with pytest.raises(ValueError, match="cannot start with a dot"):
        service._validate_filename(".hidden.md")


def test_count_words(tmp_path):
    """Test word counting."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    assert service._count_words("one two three") == 3
    assert service._count_words("one\ntwo\tthree") == 3
    assert service._count_words("") == 0
    assert service._count_words("   ") == 0
    assert service._count_words("single") == 1


def test_generate_preview_short_content(tmp_path):
    """Test preview generation for short content."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    content = "Short content"
    preview = service._generate_preview(content, max_length=250)
    assert preview == content


def test_generate_preview_exact_length(tmp_path):
    """Test preview generation for content at exact max length."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    content = "A" * 250
    preview = service._generate_preview(content, max_length=250)
    assert preview == content
    assert not preview.endswith("...")


def test_generate_preview_long_content(tmp_path):
    """Test preview generation for long content."""
    service = SystemPromptService(prompts_dir=tmp_path / "prompts")

    content = "A" * 300
    preview = service._generate_preview(content, max_length=250)
    assert len(preview) == 250
    assert preview.endswith("...")
    assert preview.count("A") == 247  # 250 - 3 for "..."


def test_directory_auto_creation(tmp_path):
    """Test that prompts directory is auto-created."""
    prompts_dir = tmp_path / "prompts"
    assert not prompts_dir.exists()

    service = SystemPromptService(prompts_dir=prompts_dir)
    assert prompts_dir.exists()

    # Should be able to create files immediately
    service.create_prompt("test.md", "Content")
    assert (prompts_dir / "test.md").exists()


def test_utf8_encoding(tmp_path):
    """Test UTF-8 encoding support."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create file with unicode characters
    content = "你好世界 こんにちは 🌍"
    (prompts_dir / "unicode.md").write_text(content, encoding="utf-8")

    service = SystemPromptService(prompts_dir=prompts_dir)
    result = service.get_prompt("unicode.md")
    assert result == content


def test_list_prompts_skips_invalid_files(tmp_path, caplog):
    """Test that listing skips files that can't be read."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create a valid file
    (prompts_dir / "valid.md").write_text("Valid content", encoding="utf-8")

    # Create an invalid file (binary content that's not UTF-8)
    invalid_file = prompts_dir / "invalid.md"
    invalid_file.write_bytes(b"\x80\x81\x82")

    service = SystemPromptService(prompts_dir=prompts_dir)
    prompts = service.list_prompts()

    # Should return only the valid file
    assert len(prompts) == 1
    assert prompts[0]["filename"] == "valid.md"

    # Should log a warning about the invalid file
    assert "Failed to read prompt file invalid.md" in caplog.text
