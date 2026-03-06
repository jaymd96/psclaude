# psclaude oracle

Use this skill when the user asks about psclaude's API, parameters, response
types, or workspace behaviour. Also consult when you need to verify how
something works before writing code that uses psclaude.

## What psclaude is

psclaude wraps the Claude Code CLI (`claude -p`) for programmatic single-shot
invocations with workspace isolation. Each `PsClaude` instance creates a
temporary directory (prefixed `claude_`), stages extensions into it, runs
Claude, and captures the response.

Zero dependencies — stdlib only, Python 3.11+.

## Two APIs

### Class API — `PsClaude`

Use when you need multiple sends, workspace inspection, or fine-grained control.

```python
from psclaude import PsClaude, OutputMode

client = PsClaude(
    output_mode=OutputMode.TEXT,
    skills=["path/to/skill.md"],
    claude_md="path/to/CLAUDE.md",
    model="sonnet",
    timeout=120,
)
response = client.send("Explain this code", input_dir="/path/to/repo")
print(response.text)
client.cleanup()
```

### Functional API — `run_claude()`

Use for one-shot operations. Auto-cleans up the workspace.

```python
from psclaude import run_claude

result = run_claude(
    lambda client: client.send("What is 2+2?"),
    model="haiku",
)
print(result.text)
```

## Constructor parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `output_mode` | `OutputMode` | `TEXT` | `TEXT` for flat response, `STRUCTURED` for file generation |
| `skills` | `Sequence[Path]` | `()` | Skill files copied to `.claude/skills/` |
| `claude_md` | `Path \| None` | `None` | CLAUDE.md copied to workspace root |
| `plugin_dirs` | `Sequence[Path]` | `()` | Passed as `--plugin-dir` to CLI |
| `marketplaces` | `Sequence[str \| dict]` | `()` | Remote marketplaces to register |
| `marketplace` | `Marketplace \| None` | `None` | Inline marketplace definition |
| `install` | `Sequence[str]` | `()` | Plugins to install from marketplaces |
| `input_dir` | `Path \| None` | `None` | Read-only input directory (symlinked as `input/`) |
| `model` | `str \| None` | `None` | Model override (e.g. `"sonnet"`, `"opus"`) |
| `max_tokens` | `int \| None` | `None` | Max response tokens |
| `timeout` | `int` | `120` | Subprocess timeout in seconds |
| `allowed_tools` | `Sequence[str] \| None` | `None` | Tool allowlist (structured mode defaults to Read/Write/Edit/Bash) |
| `permission_mode` | `str \| None` | `None` | CLI permission mode (structured defaults to `bypassPermissions`) |

## Response types

### TextResponse (output_mode=TEXT)
```python
response.text          # str — Claude's response
response.exit_code     # int — CLI exit code
response.cost_usd      # float | None
response.input_tokens  # int | None
response.output_tokens # int | None
response.duration_ms   # int | None
response.ok            # bool — exit_code == 0
```

### StructuredResponse (output_mode=STRUCTURED)
```python
response.files         # tuple[FileEntry, ...] — generated files
response.exit_code     # int
response["main.py"]    # FileEntry lookup by filename (KeyError if missing)
for entry in response: # iterate FileEntry objects
    entry.filename     # str
    entry.description  # str
    entry.path         # Path — absolute path to file on disk
```

## Workspace layout

```
/tmp/claude_xxxxxxxx/
├── CLAUDE.md              # Copied from claude_md parameter
├── .claude/skills/        # Copied from skills parameter
│   └── my-skill.md
├── input/                 # Symlink → input_dir (read-only)
└── output/                # Structured mode only — Claude writes here
```

## Key properties

```python
client.workspace      # Path — the temp directory
client.output_dir     # Path — workspace/output
client.input_dir      # Path — workspace/input (symlink)
client.output_mode    # OutputMode
client.setup_report   # SetupReport | None — plugin install results
```

## Plugin lifecycle

```python
client.setup_report           # Check install results
client.setup_report.ok        # bool — all succeeded?
client.setup_report.failed    # tuple of failed PluginResult
client.require_setup()        # Returns report or raises RuntimeError
```

## Important behaviours

- `cleanup()` removes the workspace but never follows the input symlink —
  original input files are always safe.
- `cleanup()` is idempotent — safe to call multiple times.
- `send()` accepts `input_dir=` to override the default per-call. The symlink
  is replaced, not added alongside.
- Structured mode automatically sets `--permission-mode bypassPermissions`
  and adds `--add-dir` for the output directory.
- Input directories get `--disallowedTools` for Edit/Write/Bash on that path.
