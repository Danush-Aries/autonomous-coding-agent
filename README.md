# Autonomous Coding Agent

A two-agent autonomous coding system powered by the Claude API (claude-sonnet-4-6). Given a natural-language task, it plans and codes the solution end-to-end with real tool use and persistent state.

## Architecture

```
User task (CLI)
      │
      ▼
┌─────────────────────┐
│  Initializer Agent  │  Claude claude-sonnet-4-6 → JSON plan
│  agents/initializer │  Creates workspace directory
└─────────────────────┘
      │  plan + state
      ▼
┌─────────────────────┐
│   Coding Agent      │  Claude claude-sonnet-4-6 + tool use
│   agents/coder      │  Agentic loop per step
└─────────────────────┘
      │
      ├── write_file   (tools/file_tools.py)
      ├── read_file    (tools/file_tools.py)
      ├── list_files   (tools/file_tools.py)
      └── run_command  (tools/shell_tools.py)
```

State is persisted to `state/state.json` after each step, enabling resume on interruption.

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/Dhanush-Aries/autonomous-coding-agent
cd autonomous-coding-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 4. Run
python main.py "build a fibonacci calculator"
```

## Usage

```
python main.py "build a REST API with FastAPI"   # new task
python main.py --resume                           # continue interrupted session
python main.py --demo                             # run built-in demo task
python main.py --status                           # show current state
python main.py --clear                            # clear saved state
```

## Project Structure

```
autonomous-coding-agent/
├── main.py                 # CLI entry point
├── agents/
│   ├── initializer.py      # Planning agent (Claude → JSON plan)
│   └── coder.py            # Coding agent (agentic loop with tool use)
├── tools/
│   ├── file_tools.py       # write_file, read_file, list_files
│   └── shell_tools.py      # run_command
├── state/
│   └── manager.py          # AgentState dataclass + JSON persistence
├── workspaces/             # Generated projects land here (git-ignored)
├── requirements.txt
└── .env.example
```

## Requirements

- Python 3.10+
- `ANTHROPIC_API_KEY` in `.env`
- `anthropic>=0.43.0`, `rich>=13.7.0`, `python-dotenv>=1.0.0`

## Features

- Real Claude API tool use (not simulated) via the Anthropic SDK
- Prompt caching on system prompts for cost efficiency
- Persistent state — resume mid-task after any interruption
- Rich terminal UI with colour-coded panels for every tool call
- Manual agentic loop with full visibility into each step
