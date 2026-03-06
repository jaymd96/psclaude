"""PsClaude client — the main class."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

from psclaude._detect import detect
from psclaude._models import (
    FileEntry,
    OutputMode,
    SetupReport,
    StructuredResponse,
    TextResponse,
)
from psclaude._plugins import install_plugins

_T = TypeVar("_T")

_STRUCTURED_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["filename", "description"],
                },
            },
        },
        "required": ["files"],
    },
    separators=(",", ":"),
)

_STRUCTURED_SUFFIX = (
    "\n\nWrite all output files to the `output` directory. "
    "After writing, respond with JSON listing every file you created. "
    "Each entry needs `filename` (name only, no path) and `description` "
    "(one-line summary of the file's purpose)."
)


class PsClaude:
    """Single-shot Claude Code CLI wrapper with workspace isolation.

    Creates a temporary workspace, stages extensions (skills, CLAUDE.md,
    plugins), and provides a ``send()`` method that invokes ``claude -p``
    and returns either a flat text response or a structured response with
    generated files.

    Args:
        output_mode: ``OutputMode.TEXT`` for flat text, ``OutputMode.STRUCTURED``
            for file generation with a JSON manifest.
        skills: Paths to skill markdown files. Copied into the workspace's
            ``.claude/skills/`` directory.
        claude_md: Path to a CLAUDE.md file. Copied to the workspace root.
        plugin_dirs: Paths to plugin directories. Passed via ``--plugin-dir``.
        marketplaces: Marketplace sources to register. Each is a GitHub
            ``owner/repo``, local path, git URL, or a dict with a ``source``
            key for structured sources.
        install: Plugin identifiers to install from registered marketplaces,
            e.g. ``"review-plugin@my-marketplace"``. Installed with
            ``--scope project`` so they live inside the workspace.
        input_dir: Default directory Claude can read from. Symlinked into the
            workspace as ``input/``. Can be overridden per-send.
        model: Model override (e.g. ``"sonnet"`` or ``"claude-sonnet-4-6"``).
        max_tokens: Maximum tokens for the response.
        timeout: Subprocess timeout in seconds per invocation.
        allowed_tools: Explicit tool allowlist (e.g. ``["Read", "Write", "Bash"]``).
            Defaults to ``["Read", "Write", "Edit", "Bash"]`` in structured mode.
        permission_mode: CLI permission mode. Defaults to ``"bypassPermissions"``
            in structured mode (needed for file writes), ``None`` in text mode.
    """

    def __init__(
        self,
        *,
        output_mode: OutputMode = OutputMode.TEXT,
        skills: Sequence[str | Path] = (),
        claude_md: str | Path | None = None,
        plugin_dirs: Sequence[str | Path] = (),
        marketplaces: Sequence[str | dict] = (),
        install: Sequence[str] = (),
        input_dir: str | Path | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout: int = 120,
        allowed_tools: Sequence[str] | None = None,
        permission_mode: str | None = None,
    ) -> None:
        info = detect()
        if not info.available:
            raise RuntimeError(f"Claude Code not available: {info.error}")

        self._claude_path: str = info.path  # type: ignore[assignment]
        self._output_mode = output_mode
        self._default_input_dir: Path | None = Path(input_dir).resolve() if input_dir else None
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._plugin_dirs = [Path(p).resolve() for p in plugin_dirs]

        # Permission / tool defaults for structured mode
        if output_mode == OutputMode.STRUCTURED:
            self._allowed_tools = (
                list(allowed_tools)
                if allowed_tools is not None
                else ["Read", "Write", "Edit", "Bash"]
            )
            self._permission_mode = permission_mode or "bypassPermissions"
        else:
            self._allowed_tools = list(allowed_tools) if allowed_tools is not None else []
            self._permission_mode = permission_mode

        # Build workspace
        self._workspace = Path(tempfile.mkdtemp(prefix="claude_"))
        self._setup_workspace(skills, claude_md)

        # Install marketplace plugins
        self._setup_report: SetupReport | None = None
        if marketplaces or install:
            self._setup_report = install_plugins(
                self._claude_path,
                self._workspace,
                marketplaces=marketplaces,
                plugins=install,
                timeout=timeout,
            )

        # Symlink default input dir if provided
        if self._default_input_dir is not None:
            self._link_input_dir(self._default_input_dir)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def workspace(self) -> Path:
        """Path to the temporary workspace directory."""
        return self._workspace

    @property
    def output_dir(self) -> Path:
        """Path where Claude writes files in structured mode."""
        return self._workspace / "output"

    @property
    def input_dir(self) -> Path:
        """Path to the input symlink inside the workspace."""
        return self._workspace / "input"

    @property
    def output_mode(self) -> OutputMode:
        return self._output_mode

    @property
    def setup_report(self) -> SetupReport | None:
        """Result of marketplace/plugin installation, or None if none were requested."""
        return self._setup_report

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Remove the workspace directory and all its contents.

        The symlink to the input directory is unlinked (not followed),
        so the original input files are never touched. Safe to call
        multiple times — subsequent calls are no-ops.
        """
        if self._workspace.exists():
            shutil.rmtree(self._workspace)


    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def _setup_workspace(
        self,
        skills: Sequence[str | Path],
        claude_md: str | Path | None,
    ) -> None:
        # CLAUDE.md at workspace root
        if claude_md is not None:
            src = Path(claude_md).resolve()
            shutil.copy2(src, self._workspace / "CLAUDE.md")

        # Skills into .claude/skills/
        if skills:
            skills_dir = self._workspace / ".claude" / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)
            for skill_path in skills:
                src = Path(skill_path).resolve()
                shutil.copy2(src, skills_dir / src.name)

        # Output directory for structured mode
        if self._output_mode == OutputMode.STRUCTURED:
            self.output_dir.mkdir(exist_ok=True)

    def _link_input_dir(self, source: Path) -> None:
        """Symlink an input directory into the workspace as ``input/``.

        If a symlink already exists it is replaced so per-send overrides work.
        """
        link = self.input_dir
        if link.is_symlink() or link.exists():
            link.unlink()
        os.symlink(source, link)

    def _resolve_input_dir(self, override: str | Path | None) -> Path | None:
        """Return the effective input dir for a send, applying the override."""
        if override is not None:
            resolved = Path(override).resolve()
            self._link_input_dir(resolved)
            return resolved
        return self._default_input_dir

    # ------------------------------------------------------------------
    # CLI invocation
    # ------------------------------------------------------------------

    def _build_cmd(
        self,
        prompt: str,
        *,
        system: str | None = None,
        input_dir: Path | None = None,
    ) -> list[str]:
        cmd = [self._claude_path, "-p"]

        # Prompt — append input dir reference and structured suffix as needed
        effective_prompt = prompt
        if input_dir is not None:
            effective_prompt += (
                f"\n\nReference files are available in the `input` directory "
                f"(symlinked from {input_dir}). "
                f"This directory is READ-ONLY — do not write, edit, or delete any files in it."
            )
        if self._output_mode == OutputMode.STRUCTURED:
            effective_prompt += _STRUCTURED_SUFFIX
        cmd.append(effective_prompt)

        # Output format — always JSON so we can extract metadata
        cmd.extend(["--output-format", "json"])

        # System prompt
        if system:
            cmd.extend(["--system-prompt", system])

        # Model
        if self._model:
            cmd.extend(["--model", self._model])

        # Max tokens
        if self._max_tokens is not None:
            cmd.extend(["--max-tokens", str(self._max_tokens)])

        # JSON schema for structured mode
        if self._output_mode == OutputMode.STRUCTURED:
            cmd.extend(["--json-schema", _STRUCTURED_SCHEMA])

        # Allowed tools
        if self._allowed_tools:
            cmd.extend(["--allowedTools", " ".join(self._allowed_tools)])

        # Permission mode
        if self._permission_mode:
            cmd.extend(["--permission-mode", self._permission_mode])

        # Plugin directories
        for plugin_dir in self._plugin_dirs:
            cmd.extend(["--plugin-dir", str(plugin_dir)])

        # Give Claude access to the output directory
        if self._output_mode == OutputMode.STRUCTURED:
            cmd.extend(["--add-dir", str(self.output_dir)])

        # Give Claude read access to the input directory (read-only)
        if input_dir is not None:
            cmd.extend(["--add-dir", str(input_dir)])
            input_prefix = str(input_dir)
            cmd.extend([
                "--disallowedTools",
                f"Edit({input_prefix}:*) Write({input_prefix}:*) Bash(rm:*{input_prefix}*)",
            ])

        return cmd

    def send(
        self,
        prompt: str,
        *,
        system: str | None = None,
        input_dir: str | Path | None = None,
    ) -> TextResponse | StructuredResponse:
        """Send a prompt to Claude and return the response.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.
            input_dir: Directory Claude can read from. Overrides the default
                ``input_dir`` set at init for this invocation only. Symlinked
                into the workspace as ``input/``.

        Returns:
            ``TextResponse`` when output_mode is TEXT,
            ``StructuredResponse`` when output_mode is STRUCTURED.
        """
        effective_input = self._resolve_input_dir(input_dir)
        cmd = self._build_cmd(prompt, system=system, input_dir=effective_input)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(self._workspace),
            )
        except subprocess.TimeoutExpired:
            if self._output_mode == OutputMode.TEXT:
                return TextResponse(
                    text="",
                    exit_code=-1,
                    duration_ms=self._timeout * 1000,
                )
            return StructuredResponse(
                files=(),
                exit_code=-1,
                duration_ms=self._timeout * 1000,
            )

        text, meta = _parse_json_output(result.stdout)

        if self._output_mode == OutputMode.TEXT:
            return TextResponse(
                text=text,
                exit_code=result.returncode,
                **meta,
            )

        return self._build_structured_response(text, result.returncode, meta)

    def _build_structured_response(
        self,
        text: str,
        exit_code: int,
        meta: dict[str, Any],
    ) -> StructuredResponse:
        """Parse the structured JSON manifest and pair with files on disk."""
        entries: list[FileEntry] = []

        try:
            manifest = json.loads(text)
            raw_files = manifest.get("files", [])
        except (json.JSONDecodeError, AttributeError):
            raw_files = []

        for item in raw_files:
            filename = item.get("filename", "")
            description = item.get("description", "")
            file_path = self.output_dir / filename

            entries.append(
                FileEntry(
                    filename=filename,
                    description=description,
                    path=file_path if file_path.exists() else Path(),
                )
            )

        # Pick up files Claude wrote but didn't list in the manifest
        listed = {e.filename for e in entries}
        if self.output_dir.exists():
            for child in sorted(self.output_dir.iterdir()):
                if child.is_file() and child.name not in listed:
                    entries.append(
                        FileEntry(
                            filename=child.name,
                            description="(unlisted by Claude)",
                            path=child,
                        )
                    )

        return StructuredResponse(
            files=tuple(entries),
            exit_code=exit_code,
            **meta,
        )


# ------------------------------------------------------------------
# JSON output parsing
# ------------------------------------------------------------------


def _parse_json_output(raw: str) -> tuple[str, dict[str, Any]]:
    """Parse Claude Code's ``--output-format json`` response.

    Returns (assistant_text, metadata_dict) where metadata_dict has
    optional keys: cost_usd, input_tokens, output_tokens, duration_ms.
    """
    meta: dict[str, Any] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip(), meta

    text_parts: list[str] = []

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

            if "cost_usd" in msg:
                meta["cost_usd"] = msg["cost_usd"]
                meta["input_tokens"] = msg.get("input_tokens")
                meta["output_tokens"] = msg.get("output_tokens")
            if "duration_ms" in msg:
                meta["duration_ms"] = msg["duration_ms"]

    elif isinstance(data, dict):
        text_parts.append(data.get("text", data.get("content", str(data))))

    return "\n".join(text_parts).strip(), meta


# ------------------------------------------------------------------
# Functional API
# ------------------------------------------------------------------


def run_claude(
    fn: Callable[[PsClaude], _T],
    *,
    output_mode: OutputMode = OutputMode.TEXT,
    skills: Sequence[str | Path] = (),
    claude_md: str | Path | None = None,
    plugin_dirs: Sequence[str | Path] = (),
    marketplaces: Sequence[str | dict] = (),
    install: Sequence[str] = (),
    input_dir: str | Path | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    timeout: int = 120,
    allowed_tools: Sequence[str] | None = None,
    permission_mode: str | None = None,
) -> _T:
    """Create a PsClaude client, pass it to *fn*, then clean up.

    All keyword arguments are forwarded to :class:`PsClaude`. The workspace
    is removed after *fn* returns or raises — the original ``input_dir``
    is never touched.

    Returns whatever *fn* returns.
    """
    client = PsClaude(
        output_mode=output_mode,
        skills=skills,
        claude_md=claude_md,
        plugin_dirs=plugin_dirs,
        marketplaces=marketplaces,
        install=install,
        input_dir=input_dir,
        model=model,
        max_tokens=max_tokens,
        timeout=timeout,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,
    )
    try:
        return fn(client)
    finally:
        client.cleanup()
