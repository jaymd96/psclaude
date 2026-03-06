"""Tests for marketplace and plugin installation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from psclaude import PluginResult, PsClaude, SetupReport, run_claude
from psclaude._models import ClaudeInfo, ClaudeStatus
from psclaude._plugins import install_plugins

FAKE_INFO = ClaudeInfo(
    status=ClaudeStatus.AVAILABLE,
    path="/usr/local/bin/claude",
    version="1.0.0",
)


def _fake_run_ok(cmd, **kwargs):
    """Simulate a successful subprocess.run."""
    return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()


def _fake_run_fail(cmd, **kwargs):
    """Simulate a failed subprocess.run."""
    return type("R", (), {"returncode": 1, "stdout": "", "stderr": "error"})()


# ------------------------------------------------------------------
# PluginResult / SetupReport models
# ------------------------------------------------------------------


class TestPluginModels:
    def test_plugin_result_ok(self):
        r = PluginResult(command="claude plugin install x", exit_code=0, stdout="ok", stderr="")
        assert r.ok

    def test_plugin_result_failure(self):
        r = PluginResult(command="claude plugin install x", exit_code=1, stdout="", stderr="err")
        assert not r.ok

    def test_setup_report_ok(self):
        mp = PluginResult(command="add", exit_code=0, stdout="", stderr="")
        pl = PluginResult(command="install", exit_code=0, stdout="", stderr="")
        report = SetupReport(marketplaces=(mp,), plugins=(pl,))
        assert report.ok
        assert len(report.failed) == 0

    def test_setup_report_with_failures(self):
        mp = PluginResult(command="add", exit_code=0, stdout="", stderr="")
        pl = PluginResult(command="install", exit_code=1, stdout="", stderr="err")
        report = SetupReport(marketplaces=(mp,), plugins=(pl,))
        assert not report.ok
        assert len(report.failed) == 1
        assert report.failed[0].command == "install"


# ------------------------------------------------------------------
# install_plugins function
# ------------------------------------------------------------------


class TestInstallPlugins:
    def test_adds_marketplace_string(self, tmp_path: Path):
        with patch("psclaude._plugins.subprocess.run", side_effect=_fake_run_ok) as mock:
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                marketplaces=["jaymd96/my-marketplace"],
            )

        assert report.ok
        assert len(report.marketplaces) == 1
        cmd = mock.call_args_list[0][0][0]
        assert cmd == [
            "/usr/local/bin/claude", "plugin", "marketplace", "add",
            "jaymd96/my-marketplace",
        ]

    def test_adds_marketplace_dict(self, tmp_path: Path):
        source = {"source": "github", "repo": "jaymd96/plugins"}

        with patch("psclaude._plugins.subprocess.run", side_effect=_fake_run_ok) as mock:
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                marketplaces=[source],
            )

        assert report.ok
        cmd = mock.call_args_list[0][0][0]
        # Dict sources are JSON-serialised
        assert cmd[4] == json.dumps(source, separators=(",", ":"))

    def test_installs_plugin_with_project_scope(self, tmp_path: Path):
        with patch("psclaude._plugins.subprocess.run", side_effect=_fake_run_ok) as mock:
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                plugins=["review-plugin@my-marketplace"],
            )

        assert report.ok
        assert len(report.plugins) == 1
        cmd = mock.call_args_list[0][0][0]
        assert cmd == [
            "/usr/local/bin/claude", "plugin", "install",
            "review-plugin@my-marketplace", "--scope", "project",
        ]

    def test_runs_in_workspace_cwd(self, tmp_path: Path):
        with patch("psclaude._plugins.subprocess.run", side_effect=_fake_run_ok) as mock:
            install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                marketplaces=["source"],
                plugins=["plugin@mp"],
            )

        for c in mock.call_args_list:
            assert c[1]["cwd"] == str(tmp_path)

    def test_marketplace_then_plugins_order(self, tmp_path: Path):
        calls: list[str] = []

        def track(cmd, **kwargs):
            calls.append(cmd[1])  # "plugin" always, but cmd[2] is the subcommand
            calls.append(cmd[2])
            return _fake_run_ok(cmd, **kwargs)

        with patch("psclaude._plugins.subprocess.run", side_effect=track):
            install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                marketplaces=["mp1"],
                plugins=["p1@mp1"],
            )

        # marketplace add runs before plugin install
        assert calls == ["plugin", "marketplace", "plugin", "install"]

    def test_timeout_captured(self, tmp_path: Path):
        import subprocess as sp

        with patch(
            "psclaude._plugins.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="claude", timeout=5),
        ):
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                plugins=["slow@mp"],
                timeout=5,
            )

        assert not report.ok
        assert "Timed out" in report.plugins[0].stderr

    def test_mixed_success_failure(self, tmp_path: Path):
        results = iter([_fake_run_ok(None), _fake_run_fail(None)])

        with patch("psclaude._plugins.subprocess.run", side_effect=lambda *a, **k: next(results)):
            report = install_plugins(
                "/usr/local/bin/claude",
                tmp_path,
                marketplaces=["mp1"],
                plugins=["p1@mp1"],
            )

        assert report.marketplaces[0].ok
        assert not report.plugins[0].ok
        assert not report.ok


# ------------------------------------------------------------------
# PsClaude integration
# ------------------------------------------------------------------


class TestPsClaudePluginIntegration:
    def test_no_plugins_no_report(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude()
        assert client.setup_report is None

    def test_marketplace_and_install(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                patch("psclaude._client.install_plugins") as mock_install:
            mock_install.return_value = SetupReport(marketplaces=(), plugins=())
            client = PsClaude(
                marketplaces=["jaymd96/tools"],
                install=["review@tools"],
            )

        mock_install.assert_called_once_with(
            "/usr/local/bin/claude",
            client.workspace,
            marketplaces=["jaymd96/tools"],
            plugins=["review@tools"],
            timeout=120,
        )
        assert client.setup_report is not None

    def test_setup_report_exposed(self):
        fake_report = SetupReport(
            marketplaces=(PluginResult("add", 0, "", ""),),
            plugins=(PluginResult("install", 0, "", ""),),
        )

        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                patch("psclaude._client.install_plugins", return_value=fake_report):
            client = PsClaude(
                marketplaces=["mp"],
                install=["p@mp"],
            )

        assert client.setup_report is fake_report
        assert client.setup_report.ok

    def test_run_claude_forwards_plugin_args(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                patch("psclaude._client.install_plugins") as mock_install:
            mock_install.return_value = SetupReport(marketplaces=(), plugins=())

            result = run_claude(
                lambda c: c.setup_report,
                marketplaces=["jaymd96/tools"],
                install=["review@tools"],
            )

        mock_install.assert_called_once()
        assert result is not None


# ------------------------------------------------------------------
# require_setup
# ------------------------------------------------------------------


class TestRequireSetup:
    def test_raises_when_no_plugins_requested(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude()

        with pytest.raises(RuntimeError, match="No marketplaces or plugins were requested"):
            client.require_setup()

    def test_returns_report_on_success(self):
        fake_report = SetupReport(
            marketplaces=(PluginResult("add mp", 0, "", ""),),
            plugins=(PluginResult("install p", 0, "", ""),),
        )

        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                patch("psclaude._client.install_plugins", return_value=fake_report):
            client = PsClaude(marketplaces=["mp"], install=["p@mp"])

        report = client.require_setup()
        assert report is fake_report

    def test_raises_with_details_on_failure(self):
        fake_report = SetupReport(
            marketplaces=(PluginResult("add mp", 0, "", ""),),
            plugins=(PluginResult("install bad-plugin", 1, "", "not found"),),
        )

        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                patch("psclaude._client.install_plugins", return_value=fake_report):
            client = PsClaude(marketplaces=["mp"], install=["bad-plugin@mp"])

        with pytest.raises(RuntimeError, match="Plugin setup failed") as exc_info:
            client.require_setup()

        msg = str(exc_info.value)
        assert "install bad-plugin" in msg
        assert "not found" in msg

    def test_raises_with_multiple_failures(self):
        fake_report = SetupReport(
            marketplaces=(PluginResult("add bad-mp", 1, "", "unreachable"),),
            plugins=(PluginResult("install p", 1, "", "no marketplace"),),
        )

        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                patch("psclaude._client.install_plugins", return_value=fake_report):
            client = PsClaude(marketplaces=["bad-mp"], install=["p@bad-mp"])

        with pytest.raises(RuntimeError) as exc_info:
            client.require_setup()

        msg = str(exc_info.value)
        assert "add bad-mp" in msg
        assert "unreachable" in msg
        assert "install p" in msg
        assert "no marketplace" in msg
