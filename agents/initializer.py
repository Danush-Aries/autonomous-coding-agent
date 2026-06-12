"""Initializer Agent — breaks a task into a plan and sets up the workspace."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from state.manager import AgentState, StateManager, Step
from tools.file_tools import FILE_TOOLS, execute_file_tool

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are an expert software architect and planning agent.
Your job is to break down a coding task into clear, actionable steps.

Given a task description you will:
1. Analyse what needs to be built.
2. Identify the files and components required.
3. Return a JSON plan (and only JSON) structured exactly as shown:

{
  "workspace": "<short_directory_name_for_the_project>",
  "steps": [
    {"index": 0, "description": "Create project structure and main entry point"},
    {"index": 1, "description": "Implement core logic in ..."},
    ...
  ]
}

Rules:
- workspace must be a simple directory name (no spaces, no slashes).
- Each step description must be concrete enough for a coding agent to act on.
- 3-8 steps for most tasks.
- Return ONLY the JSON — no preamble, no markdown fences."""


def _extract_json(text: str) -> dict:
    """Pull JSON from the response, even if wrapped in markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        text = inner.strip()
    return json.loads(text)


def run_initializer(
    task: str,
    console: Console,
    state_manager: StateManager,
    workspace_base: str,
) -> AgentState:
    """
    Run the Initializer Agent.

    Calls Claude to produce a plan, saves state, creates the workspace directory,
    and returns a populated AgentState ready for the Coding Agent.
    """
    console.print(Panel(
        Text(f"Task: {task}", style="bold white"),
        title="[bold cyan]Initializer Agent[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))

    client = anthropic.Anthropic()

    console.print("[dim cyan]Planning...[/dim cyan]")

    # Use prompt caching on the stable system prompt
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": f"Task: {task}"}],
    )

    raw_text = next(
        (b.text for b in response.content if b.type == "text"), ""
    )

    console.print(Panel(
        raw_text,
        title="[bold yellow]Plan (raw)[/bold yellow]",
        border_style="yellow",
        expand=False,
    ))

    try:
        plan_data = _extract_json(raw_text)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Failed to parse plan JSON: {exc}[/red]")
        raise

    workspace_name = plan_data.get("workspace", "workspace")
    workspace_path = str(Path(workspace_base) / workspace_name)
    Path(workspace_path).mkdir(parents=True, exist_ok=True)

    steps = [
        {"index": s["index"], "description": s["description"], "status": "pending"}
        for s in plan_data.get("steps", [])
    ]

    state = AgentState(
        task=task,
        workspace=workspace_path,
        plan=steps,
        current_step=0,
        status="coding",
    )
    state_manager.save(state)

    console.print(Panel(
        "\n".join(f"  [cyan]{i}.[/cyan] {s['description']}" for i, s in enumerate(steps)),
        title=f"[bold green]Plan — {len(steps)} steps[/bold green]",
        border_style="green",
        expand=False,
    ))
    console.print(f"[green]Workspace:[/green] {workspace_path}")

    return state
