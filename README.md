# TDD Agent

A multi-agent TDD pipeline built with the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agent-sdk). Reads a `ticket.md` and autonomously plans, writes tests (RED), implements (GREEN), reviews, and reports.

## Agents

| Agent | Role |
|---|---|
| **planner** | Analyzes ticket and codebase, produces implementation plan |
| **test_writer** | Writes tests that fail (RED phase) |
| **implementer** | Writes code until tests pass (GREEN phase) |
| **reviewer** | Reviews for correctness, edge cases, security — loops back if needed |
| **reporter** | Generates a final TDD report |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install claude-agent-sdk python-dotenv
```

Copy the env file and fill in your keys:

```bash
cp .env.sample .env
```

Start the LiteLLM proxy:

```bash
docker compose up -d
```

## Usage

1. Write your bug or feature in `ticket.md`.
2. Run the agent:

```bash
python main.py
```

The pipeline will print stage banners as it progresses and output a final report when done.
