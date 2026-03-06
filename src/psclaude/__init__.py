"""psclaude — Single-shot Claude Code CLI wrapper with workspace isolation."""

from psclaude.__about__ import __version__
from psclaude._client import PsClaude, run_claude
from psclaude._detect import detect
from psclaude._install import install_plugin
from psclaude._marketplace import (
    GitHubSource,
    GitSubdirSource,
    GitUrlSource,
    Marketplace,
    NpmSource,
    PipSource,
    PluginEntry,
)
from psclaude._models import (
    ClaudeInfo,
    ClaudeStatus,
    FileEntry,
    OutputMode,
    PluginResult,
    SetupReport,
    StructuredResponse,
    TextResponse,
)

__all__ = [
    "__version__",
    "ClaudeInfo",
    "ClaudeStatus",
    "FileEntry",
    "GitHubSource",
    "GitSubdirSource",
    "GitUrlSource",
    "Marketplace",
    "NpmSource",
    "OutputMode",
    "PipSource",
    "PluginEntry",
    "PluginResult",
    "PsClaude",
    "SetupReport",
    "StructuredResponse",
    "TextResponse",
    "detect",
    "install_plugin",
    "run_claude",
]
