"""Claude Code CLI detection.

Discovers the CLI binary, validates it's functional, and caches the result
for the process lifetime.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from psclaude._models import ClaudeInfo, ClaudeStatus

_cached_info: ClaudeInfo | None = None


def detect(*, force: bool = False) -> ClaudeInfo:
    """Detect whether Claude Code CLI is installed and functional.

    Results are cached for the process lifetime. Use force=True to re-check.
    """
    global _cached_info
    if _cached_info is not None and not force:
        return _cached_info

    claude_path = shutil.which("claude")
    if claude_path is None:
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
