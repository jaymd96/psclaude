#!/bin/sh
# sync-plugin.sh — Copy plugin source to the wheel-bundled location.
#
# Source of truth: plugins/psclaude-skills/
# Bundle target:   src/psclaude/_plugin/psclaude-skills/
#
# Usage:
#   ./scripts/sync-plugin.sh           Sync (copy source → bundle)
#   ./scripts/sync-plugin.sh --check   Exit 1 if out of sync (for CI)

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SRC="plugins/psclaude-skills"
DEST="src/psclaude/_plugin/psclaude-skills"

info() { printf '==> %s\n' "$1"; }
ok()   { printf '  ✓ %s\n' "$1"; }
fail() { printf '  ✗ %s\n' "$1" >&2; exit 1; }

# ── Validate source ─────────────────────────────────────────────────

[ -d "$SRC" ]              || fail "Plugin source not found: $SRC"
[ -f "$SRC/plugin.toml" ]  || fail "Missing $SRC/plugin.toml"
[ -f "$SRC/CLAUDE.md" ]    || fail "Missing $SRC/CLAUDE.md"
[ -d "$SRC/skills" ]       || fail "Missing $SRC/skills/"

SKILL_COUNT=$(find "$SRC/skills" -name '*.md' | wc -l | tr -d ' ')
[ "$SKILL_COUNT" -gt 0 ]   || fail "No .md skills found in $SRC/skills/"

# ── Check mode ───────────────────────────────────────────────────────

if [ "${1:-}" = "--check" ]; then
    if [ ! -d "$DEST" ]; then
        fail "Bundle missing: $DEST (run ./scripts/sync-plugin.sh)"
    fi
    if ! diff -rq "$SRC" "$DEST" >/dev/null 2>&1; then
        echo "Differences:"
        diff -rq "$SRC" "$DEST" || true
        fail "Plugin source and bundle are out of sync"
    fi
    ok "Plugin source and bundle are in sync"
    exit 0
fi

# ── Sync ─────────────────────────────────────────────────────────────

info "Syncing plugin: $SRC → $DEST"

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -r "$SRC" "$DEST"

ok "Copied ($SKILL_COUNT skills)"

# Verify roundtrip
if ! diff -rq "$SRC" "$DEST" >/dev/null 2>&1; then
    fail "Post-sync verification failed — files differ"
fi

ok "Verified"
