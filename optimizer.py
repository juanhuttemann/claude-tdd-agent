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


def _load_prompt(name: str, **kwargs: str) -> str:
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        template = f.read()
    return template.format(**kwargs) if kwargs else template


async def _run_query(prompt: str, target: str) -> str:
    """Run a one-shot read-only query and return collected text."""
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        cwd=target,
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


async def generate_questions(ticket: str, target: str) -> dict:
    """Analyze codebase and return {context, questions} for a vague ticket."""
    prompt = _load_prompt("optimize_questions", ticket=ticket)
    raw = await _run_query(prompt, target)
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
