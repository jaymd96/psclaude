"""Install psclaude's bundled plugin into a project."""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path


def _bundled_plugin_root() -> Path:
    """Return the path to the bundled psclaude-skills plugin directory."""
    ref = importlib.resources.files("psclaude") / "_plugin" / "psclaude-skills"
    return Path(str(ref))


def install_plugin(target: Path) -> Path:
    """Copy the bundled psclaude-skills plugin into *target*.

    *target* is typically a ``.claude/plugins/`` directory.
    Creates ``psclaude-skills/`` inside *target* with CLAUDE.md, plugin.toml,
    and skills/.

    Returns the path to the installed plugin directory.
    """
    src = _bundled_plugin_root()
    if not src.is_dir():
        msg = f"Bundled plugin not found at {src}"
        raise FileNotFoundError(msg)

    dest = target / "psclaude-skills"
    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    return dest
