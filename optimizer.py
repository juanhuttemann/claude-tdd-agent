"""Plan optimizer: generates clarifying questions from a vague ticket, then rewrites it."""

import json
import os
import re

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
OPTIMIZER_MODEL = os.getenv("OPTIMIZER_MODEL", "sonnet") or None


def _load_prompt(name: str, **kwargs: str) -> str:
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        template = f.read()
    return template.format(**kwargs) if kwargs else template


async def _run_query(prompt: str, target: str, scan_codebase: bool = True) -> str:
    """Run a one-shot read-only query and return collected text."""
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"] if scan_codebase else [],
        permission_mode="bypassPermissions",
        model=OPTIMIZER_MODEL,
        cwd=target if scan_codebase else None,
        max_turns=20,
    )
    collected: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    collected.append(block.text)
    return "\n".join(collected)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from agent text, handling markdown fences."""
    stripped = text.strip()

    # Direct parse
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # From markdown code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # First { to last }
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from agent response: {stripped[:200]}")


async def generate_questions(ticket: str, target: str, scan_codebase: bool = True) -> dict:
    """Analyze codebase (if present) and return {context, questions} for a vague ticket."""
    prompt_name = "optimize_questions" if scan_codebase else "optimize_questions_no_codebase"
    prompt = _load_prompt(prompt_name, ticket=ticket)
    raw = await _run_query(prompt, target, scan_codebase=scan_codebase)
    return _extract_json(raw)


async def rewrite_ticket(
    ticket: str, target: str, context: str, answers: list[dict]
) -> str:
    """Rewrite the ticket using user's answers. Returns the new ticket text."""
    answers_text = "\n".join(
        f"Q: {a['question']}\nA: {a['answer']}" for a in answers
    )
    prompt = _load_prompt(
        "optimize_rewrite", ticket=ticket, context=context, answers=answers_text
    )
    return await _run_query(prompt, target)
