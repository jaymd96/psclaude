# marketplace integration

Use this skill when the user wants to consume plugin marketplaces, define
inline marketplaces, or manage plugin installation programmatically.

## Trigger

The user says something like:
- "Install plugins from a marketplace"
- "Define a marketplace inline"
- "Use GitHubSource / NpmSource / PipSource"
- "How do marketplace plugins work with psclaude?"
- "Check if plugins installed correctly"

## Two ways to use marketplaces

### 1. Remote marketplaces (reference by URL/repo)

Point to an existing marketplace and install plugins from it.

```python
from psclaude import PsClaude

client = PsClaude(
    marketplaces=["jaymd96/my-marketplace"],
    install=["review-plugin@my-marketplace"],
)
client.require_setup()  # Raises if install failed
```

Marketplace sources can be:
- GitHub: `"owner/repo"`
- Local path: `"/path/to/marketplace"`
- Git URL: `"https://github.com/owner/repo.git"`
- Dict with structured source: `{"source": "github", "repo": "owner/repo", "ref": "v1.0"}`

### 2. Inline marketplaces (define programmatically)

Build a marketplace definition in code. psclaude writes `marketplace.json`
to the workspace, registers it, and auto-installs the listed plugins.

```python
from psclaude import PsClaude, Marketplace, PluginEntry, GitHubSource

mp = Marketplace(
    name="my-tools",
    owner="James",
    plugins=[
        PluginEntry(
            name="review",
            source=GitHubSource(repo="jaymd96/review-plugin", ref="v1.0"),
            description="Code review assistance",
        ),
        PluginEntry(
            name="local-tool",
            source="./plugins/local-tool",
        ),
    ],
)

client = PsClaude(marketplace=mp)
client.require_setup()
```

## Typed source definitions

All source types are frozen dataclasses. Import from `psclaude`.

### GitHubSource
```python
GitHubSource(repo="owner/repo")
GitHubSource(repo="owner/repo", ref="v1.0")
GitHubSource(repo="owner/repo", ref="main", sha="abc123")
```

### GitUrlSource
```python
GitUrlSource(url="https://github.com/owner/repo.git")
GitUrlSource(url="https://github.com/owner/repo.git", ref="v2.0")
```

### GitSubdirSource
```python
GitSubdirSource(
    url="https://github.com/owner/monorepo.git",
    path="packages/my-plugin",
    ref="main",
)
```

### NpmSource
```python
NpmSource(package="@scope/plugin-name")
NpmSource(package="@scope/plugin-name", version="^1.0", registry="https://npm.example.com")
```

### PipSource
```python
PipSource(package="my-claude-plugin")
PipSource(package="my-claude-plugin", version=">=2.0", registry="https://pypi.example.com")
```

### String source (relative path)
```python
PluginEntry(name="local", source="./plugins/local")
```

## PluginEntry

```python
PluginEntry(
    name="review",                          # Required
    source=GitHubSource(repo="a/b"),        # Required: typed source or string path
    description="Code review assistance",   # Optional
    version="1.0.0",                        # Optional
)
```

## Marketplace

```python
mp = Marketplace(
    name="my-tools",                        # Required: marketplace name
    owner="James",                          # Required: owner name
    plugins=[PluginEntry(...)],             # Required: list of plugins
)

# Serialize
mp.to_dict()                                # dict for marketplace.json
mp.to_json()                                # formatted JSON string
mp.write_to(workspace_path)                 # writes .claude-plugin/marketplace.json
```

## Combining remote and inline

You can use both `marketplaces` (remote) and `marketplace` (inline) together,
plus additional `install` targets.

```python
client = PsClaude(
    marketplaces=["acme/shared-tools"],              # Remote marketplace
    marketplace=Marketplace(                          # Inline marketplace
        name="local",
        owner="me",
        plugins=[PluginEntry(name="my-plugin", source="./plugins/my-plugin")],
    ),
    install=["formatter@shared-tools"],               # Extra install from remote
)
```

Order of operations:
1. Remote marketplaces are registered
2. Inline marketplace is written and registered
3. Inline marketplace plugins are auto-installed
4. Explicit `install` targets are installed

## Checking installation

### Quick check
```python
if client.setup_report and client.setup_report.ok:
    print("All plugins installed")
```

### Strict check (raises on failure)
```python
report = client.require_setup()  # Returns SetupReport or raises RuntimeError
```

### Detailed inspection
```python
report = client.setup_report
for r in report.marketplaces:
    print(f"Marketplace: {r.command} → exit {r.exit_code}")
for r in report.plugins:
    print(f"Plugin: {r.command} → exit {r.exit_code}")
for r in report.failed:
    print(f"FAILED: {r.command}")
    print(f"  stderr: {r.stderr}")
```

## Common mistakes

**Not calling `require_setup()`.** Plugins can fail silently. If your workflow
depends on plugins, always verify installation succeeded before sending prompts.

**Confusing `marketplaces` and `marketplace`.** `marketplaces` (plural) is for
remote sources — strings or dicts. `marketplace` (singular) is for inline
`Marketplace` objects. They serve different purposes and can be used together.

**Forgetting the `@marketplace` suffix on install.** Plugin identifiers use the
format `"plugin-name@marketplace-name"`. Just `"plugin-name"` won't resolve.

**Over-pinning sources.** Use `ref` for stability, but don't pin `sha` unless
you need exact reproducibility. Pinning SHA makes updates harder.
