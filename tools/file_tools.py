"""File read/write tools for the coding agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------ #
# Tool definitions (raw JSON schema format used with Anthropic API)
# ------------------------------------------------------------------ #

WRITE_FILE_TOOL: dict[str, Any] = {
    "name": "write_file",
    "description": (
        "Write content to a file at the given path. "
        "Creates parent directories automatically. "
        "Overwrites the file if it already exists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the workspace directory.",
            },
            "content": {
                "type": "string",
                "description": "The full content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
}

READ_FILE_TOOL: dict[str, Any] = {
    "name": "read_file",
    "description": "Read the content of a file at the given path.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the workspace directory.",
            },
        },
        "required": ["path"],
    },
}

LIST_FILES_TOOL: dict[str, Any] = {
    "name": "list_files",
    "description": "List all files in a directory (recursive). Defaults to the workspace root.",
    "input_schema": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path relative to the workspace. Defaults to '.'.",
            },
        },
        "required": [],
    },
}


# ------------------------------------------------------------------ #
# Tool implementations
# ------------------------------------------------------------------ #

def write_file(path: str, content: str, workspace: str) -> str:
    """Write content to a file, creating parent dirs as needed."""
    full_path = Path(workspace) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    size = len(content.encode("utf-8"))
    return f"Written {size} bytes to {path}"


def read_file(path: str, workspace: str) -> str:
    """Read and return file content."""
    full_path = Path(workspace) / path
    if not full_path.exists():
        return f"Error: file not found: {path}"
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error reading {path}: {exc}"


def list_files(workspace: str, directory: str = ".") -> str:
    """List files recursively under a directory."""
    base = Path(workspace) / directory
    if not base.exists():
        return f"Error: directory not found: {directory}"
    lines: list[str] = []
    for root, dirs, files in os.walk(base):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_root = Path(root).relative_to(workspace)
        for f in sorted(files):
            lines.append(str(rel_root / f))
    if not lines:
        return "(empty)"
    return "\n".join(sorted(lines))


FILE_TOOLS = [WRITE_FILE_TOOL, READ_FILE_TOOL, LIST_FILES_TOOL]


def execute_file_tool(name: str, tool_input: dict[str, Any], workspace: str) -> str:
    """Dispatch a file tool call and return its string result."""
    if name == "write_file":
        return write_file(tool_input["path"], tool_input["content"], workspace)
    if name == "read_file":
        return read_file(tool_input["path"], workspace)
    if name == "list_files":
        return list_files(workspace, tool_input.get("directory", "."))
    return f"Unknown file tool: {name}"
