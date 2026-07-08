"""Core unit tests for autonomous-coding-agent (no API key required)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Make the repo root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from state.manager import AgentState, StateManager, Step
from tools.file_tools import write_file, read_file, list_files, execute_file_tool
from tools.shell_tools import run_command, execute_shell_tool


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

class TestAgentState:
    def test_default_values(self):
        s = AgentState()
        assert s.task == ""
        assert s.workspace == ""
        assert s.plan == []
        assert s.current_step == 0
        assert s.status == "idle"

    def test_is_complete_false_empty_plan(self):
        s = AgentState()
        assert s.is_complete() is False

    def test_is_complete_true_when_all_done(self):
        s = AgentState(plan=[{"index": 0, "description": "x", "status": "done"}], current_step=1)
        assert s.is_complete() is True

    def test_mark_step_done(self):
        s = AgentState(
            plan=[{"index": 0, "description": "step0", "status": "pending"}],
            current_step=0,
        )
        s.mark_step_done("output text")
        assert s.plan[0]["status"] == "done"
        assert s.plan[0]["output"] == "output text"
        assert s.current_step == 1

    def test_mark_step_failed(self):
        s = AgentState(
            plan=[{"index": 0, "description": "step0", "status": "pending"}],
            current_step=0,
        )
        s.mark_step_failed("some error")
        assert s.plan[0]["status"] == "failed"
        assert s.plan[0]["error"] == "some error"
        # current_step does not advance on failure
        assert s.current_step == 0

    def test_add_file(self):
        s = AgentState()
        s.add_file("foo.py")
        assert "foo.py" in s.files_created
        # No duplicates
        s.add_file("foo.py")
        assert s.files_created.count("foo.py") == 1

    def test_get_steps_returns_step_objects(self):
        plan = [{"index": 0, "description": "do X", "status": "pending"}]
        s = AgentState(plan=plan)
        steps = s.get_steps()
        assert len(steps) == 1
        assert isinstance(steps[0], Step)
        assert steps[0].description == "do X"

    def test_pending_steps(self):
        plan = [
            {"index": 0, "description": "a", "status": "done"},
            {"index": 1, "description": "b", "status": "pending"},
        ]
        s = AgentState(plan=plan, current_step=1)
        pending = s.pending_steps()
        assert len(pending) == 1
        assert pending[0].description == "b"

    def test_done_steps(self):
        plan = [
            {"index": 0, "description": "a", "status": "done"},
            {"index": 1, "description": "b", "status": "pending"},
        ]
        s = AgentState(plan=plan, current_step=1)
        done = s.done_steps()
        assert len(done) == 1
        assert done[0].description == "a"

    def test_round_trip_dict(self):
        s = AgentState(task="test task", workspace="/tmp/ws", status="coding")
        d = s.to_dict()
        s2 = AgentState.from_dict(d)
        assert s2.task == "test task"
        assert s2.workspace == "/tmp/ws"
        assert s2.status == "coding"


# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------

class TestStateManager:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "state.json"
        sm = StateManager(path=path)
        state = AgentState(task="hello", workspace="/tmp/hello")
        sm.save(state)
        loaded = sm.load()
        assert loaded is not None
        assert loaded.task == "hello"

    def test_load_returns_none_when_missing(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        sm = StateManager(path=path)
        assert sm.load() is None

    def test_clear_removes_file(self, tmp_path):
        path = tmp_path / "state.json"
        sm = StateManager(path=path)
        sm.save(AgentState(task="x"))
        assert sm.exists()
        sm.clear()
        assert not sm.exists()

    def test_load_handles_corrupt_json(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{bad json")
        sm = StateManager(path=path)
        assert sm.load() is None


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------

class TestFileTools:
    def test_write_and_read_file(self, tmp_path):
        ws = str(tmp_path)
        result = write_file("hello.txt", "hello world", ws)
        assert "hello.txt" in result
        content = read_file("hello.txt", ws)
        assert content == "hello world"

    def test_write_creates_parent_dirs(self, tmp_path):
        ws = str(tmp_path)
        write_file("subdir/nested/file.py", "pass", ws)
        assert (tmp_path / "subdir" / "nested" / "file.py").exists()

    def test_read_missing_file(self, tmp_path):
        ws = str(tmp_path)
        result = read_file("missing.txt", ws)
        assert "not found" in result.lower() or "error" in result.lower()

    def test_list_files_empty(self, tmp_path):
        ws = str(tmp_path)
        result = list_files(ws)
        assert result == "(empty)"

    def test_list_files_nonempty(self, tmp_path):
        ws = str(tmp_path)
        write_file("a.py", "", ws)
        write_file("b.py", "", ws)
        result = list_files(ws)
        assert "a.py" in result
        assert "b.py" in result

    def test_list_files_missing_dir(self, tmp_path):
        ws = str(tmp_path)
        result = list_files(ws, "nonexistent")
        assert "error" in result.lower() or "not found" in result.lower()

    def test_execute_file_tool_dispatch(self, tmp_path):
        ws = str(tmp_path)
        r = execute_file_tool("write_file", {"path": "x.txt", "content": "hi"}, ws)
        assert "x.txt" in r
        r2 = execute_file_tool("read_file", {"path": "x.txt"}, ws)
        assert r2 == "hi"
        r3 = execute_file_tool("list_files", {}, ws)
        assert "x.txt" in r3

    def test_execute_file_tool_unknown(self, tmp_path):
        r = execute_file_tool("bogus", {}, str(tmp_path))
        assert "unknown" in r.lower()


# ---------------------------------------------------------------------------
# Shell tools
# ---------------------------------------------------------------------------

class TestShellTools:
    def test_run_echo(self, tmp_path):
        result = run_command("echo hello", str(tmp_path))
        assert "hello" in result

    def test_run_exit_code_nonzero(self, tmp_path):
        result = run_command("exit 1", str(tmp_path))
        assert "1" in result  # exit_code: 1 in output

    def test_execute_shell_tool_dispatch(self, tmp_path):
        r = execute_shell_tool("run_command", {"command": "echo ok"}, str(tmp_path))
        assert "ok" in r

    def test_execute_shell_tool_unknown(self, tmp_path):
        r = execute_shell_tool("bogus", {}, str(tmp_path))
        assert "unknown" in r.lower()
