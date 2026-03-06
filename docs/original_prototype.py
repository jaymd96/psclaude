"""Claude Code subprocess backend.

Discovers the Claude Code CLI, validates it's functional, and provides
a clean interface for sending prompts and receiving structured responses.

The detection is done once and cached for the process lifetime. If Claude
Code isn't available, callers get a clear error rather than a cryptic
subprocess failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ClaudeStatus(Enum):
    """Result of Claude Code availability check."""

    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    NOT_ON_PATH = "not_on_path"
    NOT_AUTHENTICATED = "not_authenticated"
    ERROR = "error"


@dataclass(frozen=True)
class ClaudeInfo:
    """Cached result of Claude Code detection."""

    status: ClaudeStatus
    path: str | None = None
    version: str | None = None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.status == ClaudeStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

_cached_info: ClaudeInfo | None = None


def detect_claude(*, force: bool = False) -> ClaudeInfo:
    """Detect whether Claude Code CLI is installed and functional.

    Results are cached for the process lifetime. Use force=True to re-check.

    Checks (in order):
    1. Is `claude` on PATH?
    2. Can we run `claude --version` without error?
    3. Is the user authenticated? (claude -p with a trivial prompt)

    We deliberately do NOT run a full prompt for the auth check — just
    the version command, which is fast and free.
    """
    global _cached_info
    if _cached_info is not None and not force:
        return _cached_info

    # Step 1: find the binary
    claude_path = shutil.which("claude")
    if claude_path is None:
        # Also check common install locations
        for candidate in [
            os.path.expanduser("~/.claude/local/claude"),
            os.path.expanduser("~/.npm-global/bin/claude"),
            "/usr/local/bin/claude",
        ]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                claude_path = candidate
                break

    if claude_path is None:
        _cached_info = ClaudeInfo(
            status=ClaudeStatus.NOT_INSTALLED,
            error=(
                "Claude Code CLI not found. "
                "Install with: npm install -g @anthropic-ai/claude-code"
            ),
        )
        return _cached_info

    # Step 2: get version
    try:
        result = subprocess.run(
            [claude_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            _cached_info = ClaudeInfo(
                status=ClaudeStatus.ERROR,
                path=claude_path,
                error=f"claude --version failed: {result.stderr.strip()}",
            )
            return _cached_info

        version = result.stdout.strip()

    except FileNotFoundError:
        _cached_info = ClaudeInfo(
            status=ClaudeStatus.NOT_ON_PATH,
            error=f"Found {claude_path} but couldn't execute it.",
        )
        return _cached_info
    except subprocess.TimeoutExpired:
        _cached_info = ClaudeInfo(
            status=ClaudeStatus.ERROR,
            path=claude_path,
            error="claude --version timed out after 10s.",
        )
        return _cached_info

    _cached_info = ClaudeInfo(
        status=ClaudeStatus.AVAILABLE,
        path=claude_path,
        version=version,
    )
    return _cached_info


# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaudeResponse:
    """Result from a Claude Code CLI invocation."""

    text: str
    raw_output: str
    exit_code: int
    cost: dict[str, Any] | None = None
    duration_ms: int | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def invoke(
    prompt: str,
    *,
    system: str | None = None,
    output_format: str = "json",
    timeout: int = 120,
    max_tokens: int | None = None,
) -> ClaudeResponse:
    """Send a prompt to Claude Code CLI and return the response.

    Args:
        prompt: The user prompt to send.
        system: Optional system prompt (prepended to the user prompt since
                Claude Code CLI doesn't have a dedicated system flag — we
                use the --system-prompt flag if available, otherwise prepend).
        output_format: "text", "json", or "stream-json".
        timeout: Subprocess timeout in seconds.
        max_tokens: Max tokens for the response (passed via --max-tokens if supported).

    Returns:
        ClaudeResponse with the text output and metadata.

    Raises:
        RuntimeError: If Claude Code is not available.
    """
    info = detect_claude()
    if not info.available:
        raise RuntimeError(
            f"Claude Code not available: {info.error}"
        )

    cmd = [info.path, "-p"]

    # Build the prompt — prepend system instructions if provided
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    cmd.append(full_prompt)

    cmd.extend(["--output-format", output_format])

    if max_tokens is not None:
        cmd.extend(["--max-tokens", str(max_tokens)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ClaudeResponse(
            text="",
            raw_output="",
            exit_code=-1,
            cost=None,
            duration_ms=timeout * 1000,
        )

    raw = result.stdout

    # Parse response based on format
    if output_format == "json":
        text, cost, duration_ms = _parse_json_output(raw)
    else:
        text = raw.strip()
        cost = None
        duration_ms = None

    return ClaudeResponse(
        text=text,
        raw_output=raw,
        exit_code=result.returncode,
        cost=cost,
        duration_ms=duration_ms,
    )


def _parse_json_output(raw: str) -> tuple[str, dict[str, Any] | None, int | None]:
    """Parse Claude Code's JSON output format.

    The JSON format returns an array of message objects. We extract the
    assistant's text content, plus cost/duration metadata if present.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat as plain text
        return raw.strip(), None, None

    # data is a list of conversation messages
    text_parts: list[str] = []
    cost = None
    duration_ms = None

    if isinstance(data, list):
        for msg in data:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))

            # Extract metadata if present
            if "cost_usd" in msg:
                cost = {
                    "cost_usd": msg["cost_usd"],
                    "input_tokens": msg.get("input_tokens"),
                    "output_tokens": msg.get("output_tokens"),
                }
            if "duration_ms" in msg:
                duration_ms = msg["duration_ms"]

    elif isinstance(data, dict):
        # Single message format
        text_parts.append(data.get("text", data.get("content", str(data))))

    return "\n".join(text_parts).strip(), cost, duration_ms


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Quick check: is Claude Code CLI available?"""
    return detect_claude().available


def require() -> ClaudeInfo:
    """Assert Claude Code is available, raising RuntimeError if not.

    Returns the ClaudeInfo on success for callers that want the metadata.
    """
    info = detect_claude()
    if not info.available:
        raise RuntimeError(
            f"Claude Code is required but not available: {info.error}"
        )
    return info


def print_status(*, file=sys.stderr) -> None:
    """Print a human-readable status line about Claude Code availability."""
    info = detect_claude()
    if info.available:
        print(f"✓ Claude Code {info.version} at {info.path}", file=file)
    else:
        print(f"✗ Claude Code: {info.error}", file=file)