#!/usr/bin/env python3
"""
Autonomous Coding Agent
=======================
Two-agent pipeline:
  1. Initializer Agent  — breaks the task into a plan
  2. Coding Agent       — executes each step with real tools

Usage:
  python main.py "build a fibonacci calculator"
  python main.py --demo                       # uses built-in sample task
  python main.py --resume                     # continue interrupted session
  python main.py --status                     # show current state
  python main.py --clear                      # clear saved state
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from state.manager import AgentState, StateManager
from agents.initializer import run_initializer
from agents.coder import run_coder

WORKSPACES_DIR = Path(__file__).parent / "workspaces"
DEMO_TASK = "build a todo CLI app with add, list, complete, and delete commands"


def _show_status(state: AgentState, console: Console) -> None:
    """Print a Rich table of current state."""
    table = Table(title="Agent State", show_header=True, header_style="bold cyan")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Task", state.task)
    table.add_row("Status", state.status)
    table.add_row("Workspace", state.workspace)
    table.add_row("Progress", f"{state.current_step}/{len(state.plan)} steps")

    console.print(table)
    console.print()

    if state.plan:
        step_table = Table(title="Plan Steps", show_header=True, header_style="bold blue")
        step_table.add_column("#", style="dim", width=4)
        step_table.add_column("Status", width=10)
        step_table.add_column("Description")

        status_colors = {
            "done": "[green]done[/green]",
            "running": "[yellow]running[/yellow]",
            "failed": "[red]failed[/red]",
            "pending": "[dim]pending[/dim]",
        }

        for s in state.plan:
            colored = status_colors.get(s["status"], s["status"])
            step_table.add_row(str(s["index"]), colored, s["description"])

        console.print(step_table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent — powered by Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", nargs="?", help="Coding task to execute")
    parser.add_argument("--demo", action="store_true", help=f"Run demo task: {DEMO_TASK!r}")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--status", action="store_true", help="Show current state and exit")
    parser.add_argument("--clear", action="store_true", help="Clear saved state and exit")
    args = parser.parse_args()

    console = Console()
    state_manager = StateManager()

    # ------------------------------------------------------------------ #
    # --clear
    # ------------------------------------------------------------------ #
    if args.clear:
        state_manager.clear()
        console.print("[green]State cleared.[/green]")
        return

    # ------------------------------------------------------------------ #
    # --status
    # ------------------------------------------------------------------ #
    if args.status:
        state = state_manager.load()
        if state is None:
            console.print("[yellow]No saved state.[/yellow]")
        else:
            _show_status(state, console)
        return

    # ------------------------------------------------------------------ #
    # --resume
    # ------------------------------------------------------------------ #
    if args.resume:
        state = state_manager.load()
        if state is None:
            console.print("[red]No saved state to resume. Run with a task first.[/red]")
            sys.exit(1)
        console.print(Panel(
            Text(f"Resuming: {state.task}\nStep {state.current_step}/{len(state.plan)}",
                 style="bold white"),
            title="[bold yellow]Resume[/bold yellow]",
            border_style="yellow",
            expand=False,
        ))
        run_coder(state, state_manager, console)
        return

    # ------------------------------------------------------------------ #
    # New task (or demo)
    # ------------------------------------------------------------------ #
    if args.demo:
        task = DEMO_TASK
    elif args.task:
        task = args.task
    else:
        parser.print_help()
        sys.exit(1)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[red]ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key.[/red]"
        )
        sys.exit(1)

    # If there is already saved state for a different task, warn
    existing = state_manager.load()
    if existing and existing.task != task and existing.status not in ("done", "failed"):
        console.print(
            f"[yellow]Warning: existing session for '{existing.task}' "
            f"(step {existing.current_step}/{len(existing.plan)}). "
            "Use --resume to continue or --clear to discard.[/yellow]"
        )
        sys.exit(1)

    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

    # Clear old state before starting fresh
    state_manager.clear()

    console.print(Panel(
        Text(
            "Autonomous Coding Agent\n"
            "Two-agent pipeline: Initializer → Coder\n"
            f"Task: {task}",
            style="bold white",
        ),
        title="[bold magenta]Autonomous Coding Agent[/bold magenta]",
        border_style="magenta",
        expand=False,
    ))

    # Phase 1: Initializer Agent
    state = run_initializer(
        task=task,
        console=console,
        state_manager=state_manager,
        workspace_base=str(WORKSPACES_DIR),
    )

    # Phase 2: Coding Agent
    state = run_coder(state, state_manager, console)

    # Final summary
    _show_status(state, console)


if __name__ == "__main__":
    main()
