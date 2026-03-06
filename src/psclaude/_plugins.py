"""Plugin and marketplace installation via the Claude Code CLI.

Runs ``claude plugin marketplace add`` and ``claude plugin install`` as
subprocess calls scoped to the workspace directory. All plugins are
installed with ``--scope project`` so they live inside the workspace's
``.claude/`` tree and are removed on cleanup.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from psclaude._marketplace import Marketplace
from psclaude._models import PluginResult, SetupReport


def install_plugins(
    claude_path: str,
    workspace: Path,
    *,
    marketplaces: Sequence[str | dict] = (),
    local_marketplace: Marketplace | None = None,
    plugins: Sequence[str] = (),
    timeout: int = 120,
) -> SetupReport:
    """Add marketplaces and install plugins into a workspace.

    Args:
        claude_path: Absolute path to the ``claude`` binary.
        workspace: Workspace directory (used as cwd and project scope root).
        marketplaces: Remote marketplace sources to add. Each is either:
            - a string: GitHub ``owner/repo``, local path, or git URL
            - a dict with ``source`` key for structured sources (github, url, etc.)
        local_marketplace: A :class:`Marketplace` definition to write into the
            workspace and register. Its plugins are automatically installed —
            no need to list them in *plugins* (though you can install additional
            plugins from remote marketplaces there).
        plugins: Extra plugin identifiers to install,
            e.g. ``"review-plugin@my-marketplace"``.
        timeout: Subprocess timeout in seconds per command.

    Returns:
        A :class:`SetupReport` summarising the results.
    """
    mp_results: list[PluginResult] = []
    pl_results: list[PluginResult] = []

    # Remote marketplaces
    for mp in marketplaces:
        mp_results.append(_add_marketplace(claude_path, workspace, mp, timeout=timeout))

    # Local (inline) marketplace — write to disk, register, auto-install its plugins
    if local_marketplace is not None:
        local_marketplace.write_to(workspace)
        mp_results.append(_add_marketplace(claude_path, workspace, ".", timeout=timeout))
        for entry in local_marketplace.plugins:
            identifier = f"{entry.name}@{local_marketplace.name}"
            pl_results.append(_install_plugin(claude_path, workspace, identifier, timeout=timeout))

    # Explicit plugin installs (from any registered marketplace)
    for plugin in plugins:
        pl_results.append(_install_plugin(claude_path, workspace, plugin, timeout=timeout))

    return SetupReport(
        marketplaces=tuple(mp_results),
        plugins=tuple(pl_results),
    )


def _add_marketplace(
    claude_path: str,
    workspace: Path,
    source: str | dict,
    *,
    timeout: int,
) -> PluginResult:
    """Run ``claude plugin marketplace add <source>``."""
    source_arg = json.dumps(source, separators=(",", ":")) if isinstance(source, dict) else source

    cmd = [claude_path, "plugin", "marketplace", "add", source_arg]
    return _run(cmd, workspace, timeout)


def _install_plugin(
    claude_path: str,
    workspace: Path,
    plugin: str,
    *,
    timeout: int,
) -> PluginResult:
    """Run ``claude plugin install <plugin> --scope project``."""
    cmd = [claude_path, "plugin", "install", plugin, "--scope", "project"]
    return _run(cmd, workspace, timeout)


def _run(cmd: list[str], workspace: Path, timeout: int) -> PluginResult:
    """Execute a CLI command and wrap the result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workspace),
        )
        return PluginResult(
            command=" ".join(cmd),
            exit_code=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return PluginResult(
            command=" ".join(cmd),
            exit_code=-1,
            stdout="",
            stderr=f"Timed out after {timeout}s",
        )
