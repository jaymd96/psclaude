"""Tests for plugin installation."""

from __future__ import annotations

from pathlib import Path

from psclaude._install import install_plugin


class TestInstallPlugin:
    def test_copies_plugin(self, tmp_path: Path):
        dest = install_plugin(tmp_path)
        assert dest == tmp_path / "psclaude-skills"
        assert (dest / "plugin.toml").exists()
        assert (dest / "CLAUDE.md").exists()
        assert (dest / "skills").is_dir()
        assert (dest / "skills" / "psclaude-oracle.md").exists()
        assert (dest / "skills" / "build-with-psclaude.md").exists()
        assert (dest / "skills" / "marketplace-integration.md").exists()

    def test_overwrites_existing(self, tmp_path: Path):
        dest = install_plugin(tmp_path)
        (dest / "marker.txt").write_text("old")
        dest2 = install_plugin(tmp_path)
        assert dest2 == dest
        assert not (dest2 / "marker.txt").exists()

    def test_plugin_toml_has_name(self, tmp_path: Path):
        dest = install_plugin(tmp_path)
        content = (dest / "plugin.toml").read_text()
        assert 'name = "psclaude-skills"' in content
