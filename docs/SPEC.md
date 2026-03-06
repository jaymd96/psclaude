# psclaude — Specification & Design Goals

This document captures the design rationale and goals for psclaude. It serves as
a reference for contributors and as a record of decisions made during the initial
build.

## Problem

Claude Code CLI is powerful but requires manual workspace setup — placing
CLAUDE.md, skills, and plugins in the right locations, managing permissions,
parsing JSON output. For programmatic use (CI pipelines, build tools, automated
workflows), this ceremony needs to be handled by a library.

## Goals

1. **Single-shot, isolated invocations** — each `send()` runs in a temporary
   workspace with no shared state between calls. No conversation history.

2. **Two output modes** — text (flat response) and structured (Claude generates
   files to disk, returns a JSON manifest listing them).

3. **Extension staging** — skills, CLAUDE.md, and plugin directories are placed
   into the workspace so Claude Code discovers them naturally.

4. **Read-only input directories** — callers can expose a directory for Claude
   to read from. Write/edit/delete operations are blocked at the CLI tool level
   and via prompt instruction.

5. **Programmatic cleanup** — `cleanup()` removes the workspace. `run_claude()`
   provides a functional wrapper that handles this automatically.

6. **Zero dependencies** — stdlib only. No runtime dependencies beyond Python 3.11+.

7. **Hatch-native** — builds, tests, linting, and publishing all through Hatch.

## Non-goals

- Multi-turn conversation management
- Streaming responses
- Direct API integration (this wraps the CLI, not the Anthropic API)
- Claude Code plugin development (see `anvil/plugin-creator` for that)

## Architecture decisions

### Workspace isolation via tmpdir

Each `PsClaude` instance creates a `tempfile.mkdtemp(prefix="claude_")` directory.
This gives us:
- Clean filesystem state per invocation
- Natural extension discovery (Claude Code walks `.claude/skills/`, reads `CLAUDE.md`)
- No interference between concurrent instances
- Simple cleanup via `shutil.rmtree`

### Symlink for input directory

The input directory is symlinked rather than copied:
- Instant setup regardless of input size
- Claude can traverse the full directory tree
- `shutil.rmtree` unlinks symlinks without following them, so cleanup never
  touches the original data

### Read-only enforcement on input

Three layers:
1. `--disallowedTools` blocks `Edit`, `Write`, and `Bash(rm)` scoped to the input path
2. Prompt instruction marks the directory as `READ-ONLY`
3. The symlink itself is just a pointer — Claude writes to `output/`, not `input/`

### JSON output format

We always use `--output-format json` internally, even for text mode. This gives
us cost metadata (USD, tokens, duration) alongside the response text. The caller
sees clean `TextResponse`/`StructuredResponse` objects.

### Structured mode schema

Structured mode uses `--json-schema` to enforce the response format:
```json
{
  "type": "object",
  "properties": {
    "files": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "filename": {"type": "string"},
          "description": {"type": "string"}
        },
        "required": ["filename", "description"]
      }
    }
  },
  "required": ["files"]
}
```

As a safety net, we also scan `output/` for files Claude wrote but didn't list
in the manifest.

## CLI flags used

| Flag | Purpose |
|---|---|
| `-p` | Non-interactive (print) mode |
| `--output-format json` | Structured CLI output with metadata |
| `--system-prompt` | System prompt injection |
| `--model` | Model override |
| `--max-tokens` | Response length cap |
| `--json-schema` | Structured output schema (structured mode) |
| `--allowedTools` | Tool allowlist |
| `--disallowedTools` | Block write tools on input directory |
| `--permission-mode` | Permission bypass for file writes |
| `--plugin-dir` | Plugin directory paths |
| `--add-dir` | Grant tool access to output/input directories |

## Reference material

- `docs/claude_help.txt` — Full `claude --help` output
- `docs/extend_claude.txt` — Claude Code extensibility documentation
- `docs/original_prototype.py` — Initial prototype this package was built from
