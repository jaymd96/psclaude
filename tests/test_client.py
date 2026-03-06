"""Tests for PsClaude client — workspace setup and command building.

These tests mock subprocess and CLI detection so they run without
Claude Code installed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from psclaude import OutputMode, PsClaude, run_claude
from psclaude._models import ClaudeInfo, ClaudeStatus

FAKE_INFO = ClaudeInfo(
    status=ClaudeStatus.AVAILABLE,
    path="/usr/local/bin/claude",
    version="1.0.0",
)


@pytest.fixture()
def text_client(tmp_path: Path):
    """PsClaude in TEXT mode with detection mocked."""
    with patch("psclaude._client.detect", return_value=FAKE_INFO):
        client = PsClaude(output_mode=OutputMode.TEXT)
    return client


@pytest.fixture()
def structured_client(tmp_path: Path):
    """PsClaude in STRUCTURED mode with detection mocked."""
    with patch("psclaude._client.detect", return_value=FAKE_INFO):
        client = PsClaude(output_mode=OutputMode.STRUCTURED)
    return client


# ------------------------------------------------------------------
# Workspace setup
# ------------------------------------------------------------------


class TestWorkspaceSetup:
    def test_workspace_created_with_prefix(self, text_client: PsClaude):
        assert text_client.workspace.exists()
        assert text_client.workspace.name.startswith("claude_")

    def test_output_dir_created_in_structured_mode(self, structured_client: PsClaude):
        assert structured_client.output_dir.exists()
        assert structured_client.output_dir.name == "output"

    def test_claude_md_copied(self, tmp_path: Path):
        md = tmp_path / "CLAUDE.md"
        md.write_text("# Test instructions")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(claude_md=md)

        assert (client.workspace / "CLAUDE.md").read_text() == "# Test instructions"

    def test_skills_copied(self, tmp_path: Path):
        skill = tmp_path / "review.md"
        skill.write_text("Review checklist")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(skills=[skill])

        copied = client.workspace / ".claude" / "skills" / "review.md"
        assert copied.exists()
        assert copied.read_text() == "Review checklist"

    def test_input_dir_symlinked_at_init(self, tmp_path: Path):
        src = tmp_path / "my_inputs"
        src.mkdir()
        (src / "data.csv").write_text("a,b,c")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(input_dir=src)

        link = client.input_dir
        assert link.is_symlink()
        assert os.readlink(str(link)) == str(src.resolve())
        assert (link / "data.csv").read_text() == "a,b,c"

    def test_no_input_dir_by_default(self, text_client: PsClaude):
        assert not text_client.input_dir.exists()


# ------------------------------------------------------------------
# Command building
# ------------------------------------------------------------------


class TestCommandBuilding:
    def test_text_mode_basic_cmd(self, text_client: PsClaude):
        cmd = text_client._build_cmd("hello")
        assert cmd[0] == "/usr/local/bin/claude"
        assert "-p" in cmd
        assert "hello" in cmd
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "json"

    def test_text_mode_no_json_schema(self, text_client: PsClaude):
        cmd = text_client._build_cmd("hello")
        assert "--json-schema" not in cmd

    def test_structured_mode_has_json_schema(self, structured_client: PsClaude):
        cmd = structured_client._build_cmd("generate code")
        assert "--json-schema" in cmd

    def test_structured_mode_appends_suffix(self, structured_client: PsClaude):
        cmd = structured_client._build_cmd("generate code")
        prompt_arg = cmd[cmd.index("-p") + 1]
        assert "Write all output files" in prompt_arg

    def test_structured_mode_has_add_dir(self, structured_client: PsClaude):
        cmd = structured_client._build_cmd("generate code")
        assert "--add-dir" in cmd
        idx = cmd.index("--add-dir")
        assert cmd[idx + 1] == str(structured_client.output_dir)

    def test_structured_mode_permission_bypass(self, structured_client: PsClaude):
        cmd = structured_client._build_cmd("generate code")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "bypassPermissions"

    def test_system_prompt(self, text_client: PsClaude):
        cmd = text_client._build_cmd("hello", system="be helpful")
        assert "--system-prompt" in cmd
        idx = cmd.index("--system-prompt")
        assert cmd[idx + 1] == "be helpful"

    def test_model_override(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(model="sonnet")
        cmd = client._build_cmd("hello")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "sonnet"

    def test_plugin_dirs(self, tmp_path: Path):
        plugin = tmp_path / "my_plugin"
        plugin.mkdir()

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(plugin_dirs=[plugin])

        cmd = client._build_cmd("hello")
        assert "--plugin-dir" in cmd
        idx = cmd.index("--plugin-dir")
        assert cmd[idx + 1] == str(plugin)

    def test_allowed_tools_override(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(
                output_mode=OutputMode.STRUCTURED,
                allowed_tools=["Write"],
            )
        cmd = client._build_cmd("hello")
        idx = cmd.index("--allowedTools")
        assert cmd[idx + 1] == "Write"

    def test_input_dir_adds_add_dir_and_prompt_ref(self, tmp_path: Path):
        src = tmp_path / "inputs"
        src.mkdir()

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(input_dir=src)

        cmd = client._build_cmd("analyse this", input_dir=src.resolve())
        # --add-dir should reference the real input path
        assert "--add-dir" in cmd
        idx = cmd.index("--add-dir")
        assert cmd[idx + 1] == str(src.resolve())
        # Prompt should mention the input directory
        prompt_arg = cmd[cmd.index("-p") + 1]
        assert "Reference files are available" in prompt_arg
        assert "READ-ONLY" in prompt_arg

    def test_input_dir_disallows_write_edit(self, tmp_path: Path):
        src = tmp_path / "inputs"
        src.mkdir()

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(input_dir=src)

        cmd = client._build_cmd("analyse this", input_dir=src.resolve())
        assert "--disallowedTools" in cmd
        idx = cmd.index("--disallowedTools")
        disallowed = cmd[idx + 1]
        assert f"Edit({src.resolve()}:*)" in disallowed
        assert f"Write({src.resolve()}:*)" in disallowed

    def test_no_input_dir_no_add_dir(self, text_client: PsClaude):
        cmd = text_client._build_cmd("hello")
        assert "--add-dir" not in cmd
        assert "--disallowedTools" not in cmd


# ------------------------------------------------------------------
# Response parsing
# ------------------------------------------------------------------


class TestSend:
    def test_text_mode_send(self, text_client: PsClaude):
        fake_output = json.dumps([
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello world"}],
            },
            {"cost_usd": 0.001, "input_tokens": 10, "output_tokens": 5, "duration_ms": 500},
        ])

        fake_result = type("R", (), {
            "stdout": fake_output,
            "stderr": "",
            "returncode": 0,
        })()

        with patch("subprocess.run", return_value=fake_result):
            resp = text_client.send("hi")

        assert resp.ok
        assert resp.text == "Hello world"
        assert resp.cost_usd == 0.001
        assert resp.duration_ms == 500

    def test_structured_mode_send(self, structured_client: PsClaude):
        # Write a file to the output dir to simulate Claude's work
        (structured_client.output_dir / "main.py").write_text("print('hi')")

        manifest = {"files": [{"filename": "main.py", "description": "Entry point"}]}
        fake_output = json.dumps([
            {
                "role": "assistant",
                "content": [{"type": "text", "text": json.dumps(manifest)}],
            },
        ])

        fake_result = type("R", (), {
            "stdout": fake_output,
            "stderr": "",
            "returncode": 0,
        })()

        with patch("subprocess.run", return_value=fake_result):
            resp = structured_client.send("generate a script")

        assert resp.ok
        assert len(resp) == 1
        assert resp["main.py"].description == "Entry point"
        assert resp["main.py"].content == "print('hi')"

    def test_structured_mode_picks_up_unlisted_files(self, structured_client: PsClaude):
        (structured_client.output_dir / "extra.txt").write_text("bonus")

        manifest = {"files": []}
        fake_output = json.dumps([
            {
                "role": "assistant",
                "content": [{"type": "text", "text": json.dumps(manifest)}],
            },
        ])
        fake_result = type("R", (), {
            "stdout": fake_output, "stderr": "", "returncode": 0,
        })()

        with patch("subprocess.run", return_value=fake_result):
            resp = structured_client.send("generate")

        assert len(resp) == 1
        assert resp["extra.txt"].description == "(unlisted by Claude)"

    def test_timeout_returns_empty_response(self, text_client: PsClaude):
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="claude", timeout=120)):
            resp = text_client.send("slow prompt")

        assert not resp.ok
        assert resp.exit_code == -1

    def test_send_with_per_call_input_dir(self, tmp_path: Path):
        src = tmp_path / "per_call_inputs"
        src.mkdir()
        (src / "readme.txt").write_text("hello")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude()

        fake_output = json.dumps([
            {"role": "assistant", "content": [{"type": "text", "text": "Got it"}]},
        ])
        fake_result = type("R", (), {
            "stdout": fake_output, "stderr": "", "returncode": 0,
        })()

        with patch("subprocess.run", return_value=fake_result) as mock_run:
            client.send("read the inputs", input_dir=src)

        # Verify symlink was created
        assert client.input_dir.is_symlink()
        assert (client.input_dir / "readme.txt").read_text() == "hello"

        # Verify --add-dir was passed to the CLI
        call_args = mock_run.call_args[0][0]
        assert "--add-dir" in call_args

    def test_send_override_replaces_symlink(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "a.txt").write_text("aaa")
        (dir_b / "b.txt").write_text("bbb")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(input_dir=dir_a)

        assert (client.input_dir / "a.txt").exists()

        fake_output = json.dumps([
            {"role": "assistant", "content": "ok"},
        ])
        fake_result = type("R", (), {
            "stdout": fake_output, "stderr": "", "returncode": 0,
        })()

        with patch("subprocess.run", return_value=fake_result):
            client.send("use b now", input_dir=dir_b)

        # Symlink should now point to dir_b
        assert (client.input_dir / "b.txt").exists()
        assert not (client.input_dir / "a.txt").exists()


# ------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_workspace(self, text_client: PsClaude):
        ws = text_client.workspace
        assert ws.exists()
        text_client.cleanup()
        assert not ws.exists()

    def test_cleanup_idempotent(self, text_client: PsClaude):
        text_client.cleanup()
        text_client.cleanup()  # should not raise

    def test_cleanup_does_not_delete_input_dir(self, tmp_path: Path):
        src = tmp_path / "precious_data"
        src.mkdir()
        (src / "important.csv").write_text("keep me")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(input_dir=src)

        # Workspace has symlink to src
        assert client.input_dir.is_symlink()

        client.cleanup()

        # Original data untouched
        assert src.exists()
        assert (src / "important.csv").read_text() == "keep me"

    def test_cleanup_removes_output_files(self, tmp_path: Path):
        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            client = PsClaude(output_mode=OutputMode.STRUCTURED)

        (client.output_dir / "generated.py").write_text("print('hi')")
        assert (client.output_dir / "generated.py").exists()

        client.cleanup()
        assert not client.output_dir.exists()


# ------------------------------------------------------------------
# Functional API
# ------------------------------------------------------------------


class TestRunClaude:
    def test_returns_fn_result(self):
        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            result = run_claude(lambda c: c.workspace)
        # workspace was a real path during the call
        assert isinstance(result, Path)

    def test_cleans_up_after_fn(self):
        captured_ws = None

        def capture(client):
            nonlocal captured_ws
            captured_ws = client.workspace
            assert captured_ws.exists()
            return "done"

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            result = run_claude(capture)

        assert result == "done"
        assert not captured_ws.exists()

    def test_cleans_up_on_exception(self):
        captured_ws = None

        def boom(client):
            nonlocal captured_ws
            captured_ws = client.workspace
            raise ValueError("oops")

        with patch("psclaude._client.detect", return_value=FAKE_INFO), \
                pytest.raises(ValueError):
            run_claude(boom)

        assert not captured_ws.exists()

    def test_forwards_kwargs(self, tmp_path: Path):
        skill = tmp_path / "review.md"
        skill.write_text("checklist")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            result = run_claude(
                lambda c: (c.workspace / ".claude" / "skills" / "review.md").read_text(),
                skills=[skill],
            )

        assert result == "checklist"

    def test_preserves_input_dir(self, tmp_path: Path):
        src = tmp_path / "data"
        src.mkdir()
        (src / "file.txt").write_text("safe")

        with patch("psclaude._client.detect", return_value=FAKE_INFO):
            run_claude(lambda c: None, input_dir=src)

        assert (src / "file.txt").read_text() == "safe"
