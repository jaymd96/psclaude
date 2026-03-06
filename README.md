# psclaude

Programmatic single-shot interface to [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) with workspace isolation.

psclaude creates an isolated temporary workspace per session, stages your extensions (skills, CLAUDE.md, plugins), and provides a clean Python API for sending prompts and receiving either flat text or structured file output. Each invocation is self-contained — no shared state, no side effects on your project.

> **Private alpha** — API surface may change before 1.0.

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated

## Install

```bash
pip install jaymd96-psclaude
```

## Quick start

### Text mode

Send a prompt, get a text response.

```python
from psclaude import PsClaude

client = PsClaude()
resp = client.send("Explain what a monad is in one sentence.")
print(resp.text)
client.cleanup()
```

### Structured mode

Claude generates files into an isolated output directory and returns a JSON manifest describing them.

```python
from psclaude import PsClaude, OutputMode

client = PsClaude(
    output_mode=OutputMode.STRUCTURED,
    skills=["./skills/python-style.md"],
    claude_md="./CLAUDE.md",
)

resp = client.send("Create a FastAPI hello-world project")

for f in resp:
    print(f"{f.filename}: {f.description}")
    print(f.content)

# Files persist in client.output_dir until cleanup
client.cleanup()
```

### Functional API

`run_claude` handles setup and teardown automatically.

```python
from psclaude import run_claude

resp = run_claude(
    lambda c: c.send("Summarise the CSV files"),
    input_dir="./data",
)
print(resp.text)
# Workspace already cleaned up
```

### Input directory

Provide a read-only reference directory that Claude can read from but never modify.

```python
client = PsClaude(input_dir="./data")
resp = client.send("Analyse the logs")

# Override per-send
resp = client.send("Now look at these", input_dir="./other-data")
client.cleanup()
```

### Extensions

Load skills, CLAUDE.md, and plugins to configure Claude's behaviour.

```python
client = PsClaude(
    skills=["./skills/review.md", "./skills/api-guide.md"],
    claude_md="./project-claude.md",
    plugin_dirs=["./my-plugin"],
    model="sonnet",
    timeout=180,
)
```

## API reference

### `PsClaude(**kwargs)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `output_mode` | `OutputMode` | `TEXT` | `TEXT` for flat text, `STRUCTURED` for file generation |
| `skills` | `Sequence[Path]` | `()` | Skill markdown files — copied into workspace `.claude/skills/` |
| `claude_md` | `Path \| None` | `None` | CLAUDE.md file — copied to workspace root |
| `plugin_dirs` | `Sequence[Path]` | `()` | Plugin directories — passed via `--plugin-dir` |
| `input_dir` | `Path \| None` | `None` | Read-only reference directory — symlinked as `input/` |
| `model` | `str \| None` | `None` | Model override (e.g. `"sonnet"`, `"opus"`) |
| `max_tokens` | `int \| None` | `None` | Max response tokens |
| `timeout` | `int` | `120` | Subprocess timeout in seconds |
| `allowed_tools` | `Sequence[str] \| None` | auto | Tool allowlist (defaults to `Read,Write,Edit,Bash` in structured mode) |
| `permission_mode` | `str \| None` | auto | CLI permission mode (defaults to `bypassPermissions` in structured mode) |

### `client.send(prompt, *, system=None, input_dir=None)`

Send a single-shot prompt. Returns `TextResponse` or `StructuredResponse` based on output mode.

- `system` — optional system prompt
- `input_dir` — override the default input directory for this call only

### `client.cleanup()`

Remove the workspace directory and all generated files. The original input directory is never touched. Safe to call multiple times.

### `run_claude(fn, **kwargs)`

Functional wrapper. Creates a `PsClaude` with the given kwargs, calls `fn(client)`, cleans up in a `finally` block, and returns whatever `fn` returns.

### Properties

| Property | Description |
|---|---|
| `client.workspace` | Path to the temporary workspace |
| `client.output_dir` | Path to the structured output directory |
| `client.input_dir` | Path to the input symlink in the workspace |
| `client.output_mode` | The configured `OutputMode` |

### Response types

**`TextResponse`**

| Field | Type | Description |
|---|---|---|
| `.text` | `str` | Claude's response text |
| `.ok` | `bool` | `True` if exit code is 0 |
| `.exit_code` | `int` | CLI process exit code |
| `.cost_usd` | `float \| None` | API cost in USD |
| `.input_tokens` | `int \| None` | Tokens consumed |
| `.output_tokens` | `int \| None` | Tokens generated |
| `.duration_ms` | `int \| None` | Wall-clock duration |

**`StructuredResponse`**

Same cost/status fields as `TextResponse`, plus:

| Field | Type | Description |
|---|---|---|
| `.files` | `tuple[FileEntry, ...]` | Generated files |
| `resp["filename"]` | `FileEntry` | Lookup by name |
| `len(resp)` | `int` | Number of files |
| `for f in resp` | iteration | Iterate over files |

**`FileEntry`**

| Field | Type | Description |
|---|---|---|
| `.filename` | `str` | File name (no path) |
| `.description` | `str` | One-line summary from Claude |
| `.path` | `Path` | Absolute path to the file on disk |
| `.content` | `str` | File contents (read on access) |

## Architecture

```
PsClaude.__init__()
  |
  +-- detect()              # Find and validate Claude Code CLI (cached)
  +-- mkdtemp(prefix="claude_")
  |     +-- CLAUDE.md       # Copied from claude_md param
  |     +-- .claude/skills/ # Copied from skills param
  |     +-- input/          # Symlink to input_dir (read-only)
  |     +-- output/         # Structured mode file output
  |
  +-- send(prompt)
  |     +-- _build_cmd()    # Assembles: claude -p <prompt> --output-format json ...
  |     +-- subprocess.run() with cwd=workspace
  |     +-- _parse_json_output() -> text + metadata
  |     +-- TextResponse | StructuredResponse
  |
  +-- cleanup()             # shutil.rmtree(workspace), input_dir untouched
```

## Development

```bash
hatch env create
hatch run test          # Run tests
hatch run cov           # Tests with coverage
hatch run lint:check    # Ruff lint
hatch run lint:fmt      # Ruff format
hatch build             # Build sdist + wheel
```

## License

MIT
