"""Marketplace and plugin source definitions.

Typed dataclasses matching the Claude Code plugin source schema. Use these
to build a workspace-local ``marketplace.json`` programmatically, or pass
them as structured marketplace sources.

Source types
------------

=============  ==========================================
Type           When to use
=============  ==========================================
GitHubSource   Public/private GitHub repos
GitUrlSource   Any git host (GitLab, Bitbucket, etc.)
GitSubdirSource  Plugin inside a monorepo subdirectory
NpmSource      npm registry packages
PipSource      PyPI / pip registry packages
=============  ==========================================

Relative paths (``"./plugins/my-plugin"``) are plain strings — no dataclass
needed. Pass them directly as the ``source`` in :class:`PluginEntry`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------
# Plugin source types
# ------------------------------------------------------------------


@dataclass(frozen=True)
class GitHubSource:
    """A plugin hosted in a GitHub repository."""

    repo: str
    ref: str | None = None
    sha: str | None = None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"source": "github", "repo": self.repo}
        if self.ref is not None:
            d["ref"] = self.ref
        if self.sha is not None:
            d["sha"] = self.sha
        return d


@dataclass(frozen=True)
class GitUrlSource:
    """A plugin hosted in any git repository."""

    url: str
    ref: str | None = None
    sha: str | None = None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"source": "url", "url": self.url}
        if self.ref is not None:
            d["ref"] = self.ref
        if self.sha is not None:
            d["sha"] = self.sha
        return d


@dataclass(frozen=True)
class GitSubdirSource:
    """A plugin in a subdirectory of a git repository (sparse clone)."""

    url: str
    path: str
    ref: str | None = None
    sha: str | None = None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"source": "git-subdir", "url": self.url, "path": self.path}
        if self.ref is not None:
            d["ref"] = self.ref
        if self.sha is not None:
            d["sha"] = self.sha
        return d


@dataclass(frozen=True)
class NpmSource:
    """A plugin distributed as an npm package."""

    package: str
    version: str | None = None
    registry: str | None = None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"source": "npm", "package": self.package}
        if self.version is not None:
            d["version"] = self.version
        if self.registry is not None:
            d["registry"] = self.registry
        return d


@dataclass(frozen=True)
class PipSource:
    """A plugin distributed as a pip package."""

    package: str
    version: str | None = None
    registry: str | None = None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"source": "pip", "package": self.package}
        if self.version is not None:
            d["version"] = self.version
        if self.registry is not None:
            d["registry"] = self.registry
        return d


PluginSourceType = GitHubSource | GitUrlSource | GitSubdirSource | NpmSource | PipSource


# ------------------------------------------------------------------
# Plugin entry
# ------------------------------------------------------------------


@dataclass(frozen=True)
class PluginEntry:
    """A single plugin listed in a marketplace.

    Args:
        name: Plugin identifier (kebab-case).
        source: Where to fetch the plugin. Either a typed source object
            or a relative path string (e.g. ``"./plugins/my-plugin"``).
        description: Brief plugin description.
        version: Plugin version string.
    """

    name: str
    source: PluginSourceType | str
    description: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        d["source"] = self.source.to_dict() if hasattr(self.source, "to_dict") else self.source
        if self.description is not None:
            d["description"] = self.description
        if self.version is not None:
            d["version"] = self.version
        return d


# ------------------------------------------------------------------
# Marketplace
# ------------------------------------------------------------------


@dataclass(frozen=True)
class Marketplace:
    """A plugin marketplace definition.

    Can be written to disk as ``.claude-plugin/marketplace.json`` inside a
    workspace, then registered with ``claude plugin marketplace add .``.

    Args:
        name: Marketplace identifier (kebab-case).
        owner: Maintainer name.
        plugins: Plugin entries to include.
        owner_email: Optional contact email.
        description: Optional marketplace description.
    """

    name: str
    owner: str
    plugins: Sequence[PluginEntry] = field(default_factory=tuple)
    owner_email: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "owner": {"name": self.owner},
            "plugins": [p.to_dict() for p in self.plugins],
        }
        if self.owner_email is not None:
            d["owner"]["email"] = self.owner_email
        if self.description is not None:
            d.setdefault("metadata", {})["description"] = self.description
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def write_to(self, workspace: Path) -> Path:
        """Write ``marketplace.json`` into ``<workspace>/.claude-plugin/``.

        Creates the directory if needed. Returns the path to the written file.
        """
        target_dir = workspace / ".claude-plugin"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "marketplace.json"
        target.write_text(self.to_json())
        return target
