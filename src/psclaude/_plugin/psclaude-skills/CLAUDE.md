# psclaude-skills

You have skills for building applications that use the `psclaude` library — a
programmatic wrapper around the Claude Code CLI with workspace isolation.

## When to use these skills

- **psclaude-oracle** — The user asks how psclaude works, what API to use, or
  needs a reference for parameters, response types, or workspace behaviour.
- **build-with-psclaude** — The user wants to build an application, script, or
  tool that invokes Claude programmatically. Covers both the class API and
  functional API, with patterns for input/output handling.
- **marketplace-integration** — The user wants to consume a plugin marketplace,
  define inline marketplaces, or install plugins programmatically. Covers typed
  source definitions, the Marketplace builder, and plugin lifecycle.

## Key principles

1. psclaude is zero-dependency (stdlib only). Code using it should not introduce
   unnecessary dependencies either.

2. Every PsClaude instance creates a temporary workspace. Always clean up — use
   `run_claude()` (auto-cleanup) or call `cleanup()` explicitly.

3. Input directories are read-only. psclaude enforces this with `--disallowedTools`
   and prompt instructions. Never circumvent this.

4. Structured mode (OutputMode.STRUCTURED) is for file generation. Text mode
   (OutputMode.TEXT) is for conversational responses. Choose based on whether
   the output is files or text, not on whether you want JSON.

5. The `run_claude()` functional API is preferred for one-shot operations.
   Use the `PsClaude` class directly only when you need multiple sends to the
   same workspace or fine-grained lifecycle control.
