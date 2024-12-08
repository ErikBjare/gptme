import os
from datetime import datetime, timedelta
from pathlib import Path

from gptme.message import Message
from gptme.util.context import (
    append_file_content,
    file_to_display_path,
    gather_fresh_context,
    get_mentioned_files,
)


def test_file_to_display_path(tmp_path):
    # Test relative path in workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file = workspace / "test.txt"
    file.touch()

    # Should show relative path when in workspace
    os.chdir(workspace)
    assert file_to_display_path(file, workspace) == Path("test.txt")

    # Should show absolute path when outside workspace
    os.chdir(tmp_path)
    assert file_to_display_path(file, workspace) == file.absolute()


def test_append_file_content(tmp_path):
    # Create test file
    file = tmp_path / "test.txt"
    file.write_text("old content")

    # Create message with file reference and timestamp
    msg = Message(
        "user",
        "check this file",
        files=[file],
        timestamp=datetime.now() - timedelta(minutes=1),
    )

    # Modify file after message timestamp
    file.write_text("new content")

    # Should show file was modified
    result = append_file_content(msg, check_modified=True)
    assert "<file was modified after message>" in result.content


def test_gather_fresh_context(tmp_path):
    # Create test files
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content 1")
    file2.write_text("content 2")

    # Create messages referencing files
    msgs = [
        Message("user", "check file1", files=[file1]),
        Message("user", "check file2", files=[file2]),
    ]

    # Should include both files in context
    context = gather_fresh_context(msgs, tmp_path)
    assert "file1.txt" in context.content
    assert "file2.txt" in context.content
    assert "content 1" in context.content
    assert "content 2" in context.content


def test_get_mentioned_files(tmp_path):
    # Create test files with different modification times
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content 1")
    file2.write_text("content 2")

    # Create messages with multiple mentions
    msgs = [
        Message("user", "check file1", files=[file1]),
        Message("user", "check file1 again", files=[file1]),
        Message("user", "check file2", files=[file2]),
    ]

    # Should sort by mentions (file1 mentioned twice)
    files = get_mentioned_files(msgs, tmp_path)
    assert files[0] == file1
    assert files[1] == file2
