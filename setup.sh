#!/bin/sh
# setup.sh — Set up the psclaude repository for development.
#
# Usage:
#   ./setup.sh           Full setup (env + lint + tests + plugin install)
#   ./setup.sh --dev     Dev environment only (env + plugin install)
#   ./setup.sh --plugin  Install the psclaude-skills plugin only
#
# Requirements: Python 3.11+, pip, hatch
# POSIX-compliant — works on Linux, macOS, and WSL.

set -eu

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# ── Helpers ──────────────────────────────────────────────────────────

info()  { printf '==> %s\n' "$1"; }
ok()    { printf '  ✓ %s\n' "$1"; }
fail()  { printf '  ✗ %s\n' "$1" >&2; exit 1; }

check_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 not found. Please install it first."
}

# ── Checks ───────────────────────────────────────────────────────────

check_python() {
    check_cmd python3
    PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYMAJOR=$(echo "$PYVER" | cut -d. -f1)
    PYMINOR=$(echo "$PYVER" | cut -d. -f2)
    if [ "$PYMAJOR" -lt 3 ] || { [ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 11 ]; }; then
        fail "Python 3.11+ required (found $PYVER)"
    fi
    ok "Python $PYVER"
}

check_hatch() {
    check_cmd hatch
    ok "hatch $(hatch --version 2>/dev/null || echo '(version unknown)')"
}

# ── Actions ──────────────────────────────────────────────────────────

setup_env() {
    info "Setting up development environment"
    check_python
    check_hatch

    info "Creating hatch environments"
    hatch env create 2>/dev/null || true
    ok "Default environment ready"

    hatch env create lint 2>/dev/null || true
    ok "Lint environment ready"
}

run_lint() {
    info "Running lint checks"
    hatch run lint:check
    ok "Lint passed"
}

run_tests() {
    info "Running tests"
    hatch run test
    ok "Tests passed"
}

install_plugin() {
    info "Installing psclaude-skills plugin"

    PLUGIN_SRC="$REPO_ROOT/plugins/psclaude-skills"
    PLUGIN_DEST="$REPO_ROOT/.claude/plugins/psclaude-skills"

    if [ ! -d "$PLUGIN_SRC" ]; then
        fail "Plugin source not found at $PLUGIN_SRC"
    fi

    mkdir -p "$REPO_ROOT/.claude/plugins"

    # Remove stale install, copy fresh
    rm -rf "$PLUGIN_DEST"
    cp -r "$PLUGIN_SRC" "$PLUGIN_DEST"

    ok "Installed to $PLUGIN_DEST"
}

# ── Main ─────────────────────────────────────────────────────────────

MODE="${1:-full}"

case "$MODE" in
    --dev)
        setup_env
        install_plugin
        ;;
    --plugin)
        install_plugin
        ;;
    --help|-h)
        head -8 "$0" | tail -6
        exit 0
        ;;
    full|*)
        setup_env
        run_lint
        run_tests
        install_plugin
        ;;
esac

info "Done"
