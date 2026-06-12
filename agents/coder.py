"""Coding Agent — executes each step of the plan using real tool calls."""

from __future__ import annotations

import json
from typing import Any

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.text import Text

from state.manager import AgentState, StateManager
from tools.file_tools import FILE_TOOLS, execute_file_tool
from tools.shell_tools import SHELL_TOOLS, execute_shell_tool

MODEL = "claude-sonnet-4-6"

ALL_TOOLS = FILE_TOOLS + SHELL_TOOLS

SYSTEM_PROMPT = """\
You are an expert software engineer and coding agent.
You will be given a single step to implement as part of a larger project.

You have access to these tools:
- write_file: Write or overwrite a file (path relative to workspace).
- read_file:  Read a file (path relative to workspace).
- list_files: List all files in the workspace.
- run_command: Run a shell command in the workspace (e.g. python, pip).

Rules:
- Implement the step completely — write real, working code.
- Use write_file to create every file that is needed.
- After writing code files, use run_command to validate them (e.g. python -m py_compile).
- Do NOT create placeholder or stub code — the code must actually work.
- When the step is complete, output a brief summary of what you did."""


def _render_tool_call(name: str, tool_input: dict[str, Any], console: Console) -> None:
    """Render a tool call in a styled panel."""
    if name == "write_file":
        path = tool_input.get("path", "?")
        content = tool_input.get("content", "")
        # Detect language from extension
        ext = path.rsplit(".", 1)[-1] if "." in path else "text"
        lang_map = {"py": "python", "js": "javascript", "ts": "typescript",
                    "sh": "bash", "md": "markdown", "json": "json", "txt": "text",
                    "toml": "toml", "yaml": "yaml", "yml": "yaml", "cfg": "ini",
                    "html": "html", "css": "css"}
        lang = lang_map.get(ext, "text")
        syntax = Syntax(content, lang, theme="monokai", line_numbers=True, word_wrap=True)
        console.print(Panel(
            syntax,
            title=f"[bold magenta]write_file[/bold magenta]: [cyan]{path}[/cyan]",
            border_style="magenta",
            expand=False,
        ))
    elif name == "run_command":
        cmd = tool_input.get("command", "")
        console.print(Panel(
            Text(f"$ {cmd}", style="bold green"),
            title="[bold green]run_command[/bold green]",
            border_style="green",
            expand=False,
        ))
    elif name == "read_file":
        path = tool_input.get("path", "?")
        console.print(f"  [dim]read_file:[/dim] [cyan]{path}[/cyan]")
    elif name == "list_files":
        directory = tool_input.get("directory", ".")
        console.print(f"  [dim]list_files:[/dim] [cyan]{directory}[/cyan]")


def _render_tool_result(name: str, result: str, console: Console) -> None:
    """Render a tool result."""
    if name == "run_command":
        console.print(Panel(
            Text(result, style="dim"),
            title="[dim]Output[/dim]",
            border_style="dim",
            expand=False,
        ))
    elif name == "read_file":
        console.print(Panel(
            Text(result[:2000] + ("..." if len(result) > 2000 else ""), style="dim"),
            title="[dim]File content[/dim]",
            border_style="dim",
            expand=False,
        ))
    elif name in ("write_file", "list_files"):
        console.print(f"  [dim]{result}[/dim]")


def execute_step(
    step_description: str,
    step_index: int,
    total_steps: int,
    task: str,
    workspace: str,
    done_steps: list[dict],
    console: Console,
) -> str:
    """
    Run one step with the Coding Agent.

    Uses a manual agentic loop so we can render each tool call/result with Rich.
    Returns the agent's final summary text.
    """
    console.print(Panel(
        Text(f"Step {step_index + 1}/{total_steps}: {step_description}", style="bold white"),
        title="[bold blue]Coding Agent[/bold blue]",
        border_style="blue",
        expand=False,
    ))

    client = anthropic.Anthropic()

    # Build context for the agent
    done_summary = ""
    if done_steps:
        done_summary = "\n\nCompleted steps:\n" + "\n".join(
            f"  [{s['index']}] {s['description']} — {s.get('output', 'done')[:120]}"
            for s in done_steps
        )

    user_message = (
        f"Overall task: {task}\n"
        f"Workspace directory: {workspace}\n"
        f"{done_summary}\n\n"
        f"Your current step to implement:\n{step_description}"
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    # Agentic loop — keep going until Claude stops calling tools
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=ALL_TOOLS,
            messages=messages,
        )

        # Show any text the agent emits
        for block in response.content:
            if block.type == "text" and block.text.strip():
                console.print(Panel(
                    Text(block.text.strip(), style="white"),
                    title="[bold yellow]Agent[/bold yellow]",
                    border_style="yellow",
                    expand=False,
                ))

        if response.stop_reason == "end_turn":
            # Done — extract final text
            final_text = next(
                (b.text for b in response.content if b.type == "text"), "Step complete."
            )
            return final_text

        if response.stop_reason != "tool_use":
            return f"Unexpected stop_reason: {response.stop_reason}"

        # Collect tool calls
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": response.content})

        tool_results: list[dict[str, Any]] = []
        for tool in tool_use_blocks:
            tool_input = tool.input if isinstance(tool.input, dict) else json.loads(tool.input)
            _render_tool_call(tool.name, tool_input, console)

            # Dispatch to the appropriate tool
            if tool.name in ("write_file", "read_file", "list_files"):
                result = execute_file_tool(tool.name, tool_input, workspace)
            elif tool.name == "run_command":
                result = execute_shell_tool(tool.name, tool_input, workspace)
            else:
                result = f"Unknown tool: {tool.name}"

            _render_tool_result(tool.name, result, console)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})


def run_coder(
    state: AgentState,
    state_manager: StateManager,
    console: Console,
) -> AgentState:
    """
    Run the Coding Agent over all pending steps.

    Resumes from state.current_step, saves progress after each step.
    """
    steps = state.get_steps()
    total = len(steps)

    console.print(Panel(
        Text(
            f"Task: {state.task}\n"
            f"Workspace: {state.workspace}\n"
            f"Steps: {state.current_step}/{total} completed",
            style="white",
        ),
        title="[bold blue]Coding Agent — Starting[/bold blue]",
        border_style="blue",
        expand=False,
    ))

    while not state.is_complete():
        step = state.get_current_step()
        if step is None:
            break

        # Mark as running and save checkpoint
        state.plan[state.current_step]["status"] = "running"
        state_manager.save(state)

        done = state.done_steps()

        try:
            output = execute_step(
                step_description=step.description,
                step_index=state.current_step,
                total_steps=total,
                task=state.task,
                workspace=state.workspace,
                done_steps=[s.__dict__ for s in done],
                console=console,
            )
            state.mark_step_done(output)
            console.print(f"[green]Step {state.current_step}/{total} done.[/green]")
        except Exception as exc:
            error_msg = str(exc)
            state.mark_step_failed(error_msg)
            console.print(f"[red]Step failed: {error_msg}[/red]")
            # Stop on failure
            break

        state_manager.save(state)

    if state.is_complete():
        state.status = "done"
        state_manager.save(state)
        console.print(Panel(
            Text(f"All {total} steps completed!\nWorkspace: {state.workspace}", style="bold green"),
            title="[bold green]Done[/bold green]",
            border_style="green",
            expand=False,
        ))
    else:
        console.print("[yellow]Coding agent stopped before completing all steps.[/yellow]")

    return state
