"""Response types and enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OutputMode(Enum):
    """How Claude should deliver its response."""

    TEXT = "text"
    STRUCTURED = "structured"


class ClaudeStatus(Enum):
    """Result of Claude Code availability check."""

    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    NOT_ON_PATH = "not_on_path"
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


@dataclass(frozen=True)
class TextResponse:
    """Response from text output mode."""

    text: str
    exit_code: int
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class FileEntry:
    """A single file produced by Claude in structured mode."""

    filename: str
    description: str
    path: Path = field(default=Path())

    @property
    def content(self) -> str:
        return self.path.read_text()


@dataclass(frozen=True)
class StructuredResponse:
    """Response from structured output mode."""

    files: tuple[FileEntry, ...]
    exit_code: int
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __getitem__(self, filename: str) -> FileEntry:
        for f in self.files:
            if f.filename == filename:
                return f
        raise KeyError(filename)

    def __len__(self) -> int:
        return len(self.files)

    def __iter__(self):
        return iter(self.files)


@dataclass(frozen=True)
class PluginResult:
    """Result of a single plugin CLI operation."""

    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class SetupReport:
    """Summary of marketplace and plugin installation during workspace setup."""

    marketplaces: tuple[PluginResult, ...]
    plugins: tuple[PluginResult, ...]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.marketplaces) and all(r.ok for r in self.plugins)

    @property
    def failed(self) -> tuple[PluginResult, ...]:
        return tuple(r for r in (*self.marketplaces, *self.plugins) if not r.ok)
