"""Shell command execution tool for the coding agent."""

from __future__ import annotations

import subprocess
import os
from typing import Any


RUN_COMMAND_TOOL: dict[str, Any] = {
    "name": "run_command",
    "description": (
        "Execute a shell command in the workspace directory and return stdout + stderr. "
        "Use for running tests, installing packages, checking syntax, etc. "
        "Commands run with a 60-second timeout."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute (e.g. 'python main.py', 'pip install requests').",
            },
        },
        "required": ["command"],
    },
}

SHELL_TOOLS = [RUN_COMMAND_TOOL]


def run_command(command: str, workspace: str) -> str:
    """Run a shell command in the workspace and return combined output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        parts: list[str] = []
        if result.stdout.strip():
            parts.append(f"stdout:\n{result.stdout.strip()}")
        if result.stderr.strip():
            parts.append(f"stderr:\n{result.stderr.strip()}")
        parts.append(f"exit_code: {result.returncode}")
        return "\n".join(parts) if parts else f"(no output) exit_code: {result.returncode}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 60 seconds"
    except Exception as exc:
        return f"Error executing command: {exc}"


def execute_shell_tool(name: str, tool_input: dict[str, Any], workspace: str) -> str:
    """Dispatch a shell tool call."""
    if name == "run_command":
        return run_command(tool_input["command"], workspace)
    return f"Unknown shell tool: {name}"
