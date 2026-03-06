"""Tests for response models."""

from pathlib import Path

import pytest

from psclaude import (
    ClaudeInfo,
    ClaudeStatus,
    FileEntry,
    OutputMode,
    StructuredResponse,
    TextResponse,
)


def test_claude_info_available():
    info = ClaudeInfo(status=ClaudeStatus.AVAILABLE, path="/usr/bin/claude", version="1.0.0")
    assert info.available is True


def test_claude_info_not_installed():
    info = ClaudeInfo(status=ClaudeStatus.NOT_INSTALLED, error="not found")
    assert info.available is False


def test_text_response_ok():
    r = TextResponse(text="hello", exit_code=0)
    assert r.ok is True
    assert r.text == "hello"


def test_text_response_failure():
    r = TextResponse(text="", exit_code=1)
    assert r.ok is False


def test_structured_response_lookup():
    entry = FileEntry(filename="main.py", description="entry point", path=Path())
    resp = StructuredResponse(files=(entry,), exit_code=0)
    assert resp.ok is True
    assert len(resp) == 1
    assert resp["main.py"].description == "entry point"


def test_structured_response_missing_key():
    resp = StructuredResponse(files=(), exit_code=0)
    with pytest.raises(KeyError):
        resp["nope"]


def test_structured_response_iteration():
    entries = (
        FileEntry(filename="a.py", description="a", path=Path()),
        FileEntry(filename="b.py", description="b", path=Path()),
    )
    resp = StructuredResponse(files=entries, exit_code=0)
    names = [f.filename for f in resp]
    assert names == ["a.py", "b.py"]


def test_output_mode_values():
    assert OutputMode.TEXT.value == "text"
    assert OutputMode.STRUCTURED.value == "structured"
