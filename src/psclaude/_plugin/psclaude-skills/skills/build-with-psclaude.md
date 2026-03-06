# build with psclaude

Use this skill when the user wants to build an application, script, or tool
that invokes Claude programmatically via psclaude.

## Trigger

The user says something like:
- "Build a tool that uses Claude to review code"
- "I want to automate X with Claude"
- "Write a script that sends prompts to Claude"
- "How do I use psclaude in my project?"

## Choosing the right API

**Use `run_claude()`** (functional) when:
- Single prompt, get result, done
- No need to inspect the workspace during execution
- Want guaranteed cleanup

**Use `PsClaude` class** when:
- Multiple sends to the same workspace (iterative refinement)
- Need to inspect workspace between sends
- Need to keep the workspace alive after getting the response
- Building a long-lived service that reuses the client

## Pattern: One-shot text query

The simplest use case — ask Claude something, get text back.

```python
from psclaude import run_claude

answer = run_claude(
    lambda c: c.send("Explain the difference between asyncio and threading"),
)
print(answer.text)
```

## Pattern: Code generation with file output

Use structured mode when Claude should produce files.

```python
from psclaude import PsClaude, OutputMode

client = PsClaude(output_mode=OutputMode.STRUCTURED)
response = client.send("Create a FastAPI app with health check and user CRUD endpoints")

for entry in response:
    print(f"{entry.filename}: {entry.description}")
    print(entry.path.read_text())

client.cleanup()
```

## Pattern: Analyse a codebase

Use `input_dir` to give Claude read-only access to existing code.

```python
from psclaude import run_claude

result = run_claude(
    lambda c: c.send("Review this code for security issues"),
    input_dir="/path/to/project/src",
)
print(result.text)
```

## Pattern: Use skills and CLAUDE.md

Load context and instructions for specialised tasks.

```python
from psclaude import run_claude

result = run_claude(
    lambda c: c.send("Review the API handlers"),
    skills=["skills/security-review.md", "skills/api-patterns.md"],
    claude_md="project-context/CLAUDE.md",
    input_dir="/path/to/api/src",
)
```

## Pattern: Multiple sends to one workspace

When you need iterative interaction with the same workspace.

```python
from psclaude import PsClaude, OutputMode

client = PsClaude(
    output_mode=OutputMode.STRUCTURED,
    input_dir="/path/to/existing/code",
)

try:
    # First pass: generate
    r1 = client.send("Create a test suite for the auth module")

    # Second pass: refine based on first output
    r2 = client.send("Add edge case tests for expired tokens and rate limiting")

    for entry in r2:
        print(f"  {entry.filename}")
finally:
    client.cleanup()
```

## Pattern: With marketplace plugins

Install plugins before sending prompts.

```python
from psclaude import run_claude

result = run_claude(
    lambda c: (
        c.require_setup(),
        c.send("Review this PR for issues"),
    )[-1],
    marketplaces=["acme/code-review-tools"],
    install=["review-plugin@code-review-tools"],
    input_dir="/path/to/pr/diff",
)
```

## Pattern: Error handling

```python
from psclaude import PsClaude, detect

# Check CLI availability first
info = detect()
if not info.available:
    print(f"Claude not available: {info.error}")
    exit(1)

client = PsClaude(model="sonnet", timeout=60)
try:
    response = client.send("Generate a migration script")
    if not response.ok:
        print(f"Claude returned exit code {response.exit_code}")
    else:
        print(response.text)
finally:
    client.cleanup()
```

## Common mistakes

**Forgetting cleanup.** Every `PsClaude` instance creates a temp directory.
If you use the class directly, always call `cleanup()` in a `finally` block.
Use `run_claude()` to avoid this entirely.

**Using structured mode for text questions.** Structured mode adds output
directory scaffolding, file manifest expectations, and permission bypasses.
If you just want a text answer, use `OutputMode.TEXT` (the default).

**Not checking `response.ok`.** A non-zero exit code means Claude encountered
an error. Always check before using the response content.

**Hardcoding model names.** Use short names (`"sonnet"`, `"opus"`, `"haiku"`)
rather than full model IDs. They're more readable and forward-compatible.

**Writing to the input directory.** psclaude enforces read-only on input dirs
with `--disallowedTools`. Don't try to work around this — if you need
read-write access, use `--add-dir` via the CLI directly instead of psclaude.
