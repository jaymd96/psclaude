"""Tests for marketplace and plugin source types."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from psclaude import (
    GitHubSource,
    GitSubdirSource,
    GitUrlSource,
    Marketplace,
    NpmSource,
    PipSource,
    PluginEntry,
    PsClaude,
    SetupReport,
    run_claude,
)
from psclaude._models import ClaudeInfo, ClaudeStatus

FAKE_INFO = ClaudeInfo(
    status=ClaudeStatus.AVAILABLE,
    path="/usr/local/bin/claude",
    version="1.0.0",
)


# ------------------------------------------------------------------
# Source types
# ------------------------------------------------------------------


class TestSourceTypes:
    def test_github_minimal(self):
        s = GitHubSource(repo="owner/repo")
        assert s.to_dict() == {"source": "github", "repo": "owner/repo"}

    def test_github_pinned(self):
        s = GitHubSource(repo="owner/repo", ref="v2.0", sha="abc123")
        d = s.to_dict()
        assert d["ref"] == "v2.0"
        assert d["sha"] == "abc123"

    def test_git_url_minimal(self):
        s = GitUrlSource(url="https://gitlab.com/team/plugin.git")
        assert s.to_dict() == {"source": "url", "url": "https://gitlab.com/team/plugin.git"}

    def test_git_url_pinned(self):
        s = GitUrlSource(url="https://gitlab.com/team/plugin.git", ref="main")
        assert s.to_dict()["ref"] == "main"

    def test_git_subdir(self):
        s = GitSubdirSource(
            url="https://github.com/acme/monorepo.git",
            path="tools/claude-plugin",
        )
        d = s.to_dict()
        assert d["source"] == "git-subdir"
        assert d["path"] == "tools/claude-plugin"

    def test_git_subdir_pinned(self):
        s = GitSubdirSource(
            url="https://github.com/acme/monorepo.git",
            path="tools/plugin",
            ref="v1.0",
            sha="deadbeef" * 5,
        )
        d = s.to_dict()
        assert d["ref"] == "v1.0"
        assert d["sha"] == "deadbeef" * 5

    def test_npm_minimal(self):
        s = NpmSource(package="@acme/claude-plugin")
        assert s.to_dict() == {"source": "npm", "package": "@acme/claude-plugin"}

    def test_npm_full(self):
        s = NpmSource(package="@acme/plugin", version="^2.0.0", registry="https://npm.example.com")
        d = s.to_dict()
        assert d["version"] == "^2.0.0"
        assert d["registry"] == "https://npm.example.com"

    def test_pip_minimal(self):
        s = PipSource(package="my-claude-plugin")
        assert s.to_dict() == {"source": "pip", "package": "my-claude-plugin"}

    def test_pip_full(self):
        s = PipSource(package="my-plugin", version=">=1.0", registry="https://pypi.example.com")
        d = s.to_dict()
        assert d["version"] == ">=1.0"
        assert d["registry"] == "https://pypi.example.com"


# ------------------------------------------------------------------
# PluginEntry
# ------------------------------------------------------------------


class TestPluginEntry:
    def test_with_typed_source(self):
        entry = PluginEntry(
            name="review",
            source=GitHubSource(repo="jaymd96/review-plugin"),
            description="Code review skill",
        )
        d = entry.to_dict()
        assert d["name"] == "review"
        assert d["source"] == {"source": "github", "repo": "jaymd96/review-plugin"}
        assert d["description"] == "Code review skill"

    def test_with_relative_path(self):
        entry = PluginEntry(name="local-plugin", source="./plugins/local")
        d = entry.to_dict()
        assert d["source"] == "./plugins/local"

    def test_optional_fields_omitted(self):
        entry = PluginEntry(name="minimal", source="./plugin")
        d = entry.to_dict()
        assert "description" not in d
        assert "version" not in d

    def test_version_included(self):
        entry = PluginEntry(name="versioned", source="./plugin", version="1.2.3")
        assert entry.to_dict()["version"] == "1.2.3"


# ------------------------------------------------------------------
# Marketplace
# ------------------------------------------------------------------


class TestMarketplace:
    def test_to_dict_minimal(self):
        mp = Marketplace(name="my-tools", owner="James")
        d = mp.to_dict()
        assert d["name"] == "my-tools"
        assert d["owner"] == {"name": "James"}
        assert d["plugins"] == []

    def test_to_dict_full(self):
        mp = Marketplace(
            name="my-tools",
            owner="James",
            owner_email="james@example.com",
            description="Internal dev tools",
            plugins=[
                PluginEntry(
                    name="formatter",
                    source=GitHubSource(repo="jaymd96/formatter"),
                    description="Auto-format code",
                ),
            ],
        )
        d = mp.to_dict()
        assert d["owner"]["email"] == "james@example.com"
        assert d["metadata"]["description"] == "Internal dev tools"
        assert len(d["plugins"]) == 1
        assert d["plugins"][0]["name"] == "formatter"

    def test_to_json(self):
        mp = Marketplace(
            name="test",
            owner="Test",
            plugins=[PluginEntry(name="p", source="./p")],
        )
        parsed = json.loads(mp.to_json())
        assert parsed["name"] == "test"
        assert parsed["plugins"][0]["source"] == "./p"

    def test_write_to(self, tmp_path: Path):
        mp = Marketplace(
            name="local-mp",
            owner="Test",
            plugins=[
                PluginEntry(name="review", source=GitHubSource(repo="a/b")),
            ],
        )
        result_path = mp.write_to(tmp_path)

        assert result_path == tmp_path / ".claude-plugin" / "marketplace.json"
        assert result_path.exists()

        written = json.loads(result_path.read_text())
        assert written["name"] == "local-mp"
        assert written["plugins"][0]["source"]["repo"] == "a/b"


# ------------------------------------------------------------------
# Integration with _plugins.install_plugins
# ------------------------------------------------------------------


class TestLocalMarketplaceInstall:
    def test_writes_marketplace_and_adds_dot(self, tmp_path: Path):
        mp = Marketplace(
            name="ws-plugins",
            owner="psclaude",
            plugins=[
                PluginEntry(name="review", source=GitHubSource(repo="a/b")),
                PluginEntry(name="lint", source="./plugins/lint"),
            ],
        )

        from psclaude._plugins import install_plugins

        def fake_run(cmd, **kwargs):
            return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        with patch("psclaude._plugins.subprocess.run", side_effect=fake_run) as mock:
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                local_marketplace=mp,
            )

        # marketplace.json should be on disk
        assert (tmp_path / ".claude-plugin" / "marketplace.json").exists()

        # Should have 1 marketplace add (.) + 2 plugin installs
        assert len(report.marketplaces) == 1
        assert len(report.plugins) == 2

        calls = [c[0][0] for c in mock.call_args_list]

        # First call: marketplace add .
        assert calls[0] == ["/usr/local/bin/claude", "plugin", "marketplace", "add", "."]

        # Plugin installs use name@marketplace-name format
        assert calls[1] == [
            "/usr/local/bin/claude",
            "plugin",
            "install",
            "review@ws-plugins",
            "--scope",
            "project",
        ]
        assert calls[2] == [
            "/usr/local/bin/claude",
            "plugin",
            "install",
            "lint@ws-plugins",
            "--scope",
            "project",
        ]

    def test_remote_and_local_combined(self, tmp_path: Path):
        mp = Marketplace(
            name="local",
            owner="test",
            plugins=[PluginEntry(name="local-p", source="./p")],
        )

        from psclaude._plugins import install_plugins

        def fake_run(cmd, **kwargs):
            return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        with patch("psclaude._plugins.subprocess.run", side_effect=fake_run):
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                marketplaces=["jaymd96/remote-tools"],
                local_marketplace=mp,
                plugins=["extra@jaymd96-remote-tools"],
            )

        # 2 marketplace adds (remote + local ".") + 2 plugin installs
        assert len(report.marketplaces) == 2
        assert len(report.plugins) == 2
        assert report.ok


# ------------------------------------------------------------------
# PsClaude integration
# ------------------------------------------------------------------


class TestPsClaudeMarketplaceIntegration:
    def test_marketplace_param_forwarded(self):
        mp = Marketplace(
            name="inline",
            owner="test",
            plugins=[PluginEntry(name="p", source=GitHubSource(repo="a/b"))],
        )

        with (
            patch("psclaude._client.detect", return_value=FAKE_INFO),
            patch("psclaude._client.install_plugins") as mock_install,
        ):
            mock_install.return_value = SetupReport(marketplaces=(), plugins=())
            PsClaude(marketplace=mp)

        _, kwargs = mock_install.call_args
        assert kwargs["local_marketplace"] is mp

    def test_run_claude_forwards_marketplace(self):
        mp = Marketplace(name="inline", owner="test", plugins=[])

        with (
            patch("psclaude._client.detect", return_value=FAKE_INFO),
            patch("psclaude._client.install_plugins") as mock_install,
        ):
            mock_install.return_value = SetupReport(marketplaces=(), plugins=())
            run_claude(lambda c: None, marketplace=mp)

        _, kwargs = mock_install.call_args
        assert kwargs["local_marketplace"] is mp
