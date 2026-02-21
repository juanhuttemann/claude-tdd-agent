from dataclasses import dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from events import EventBus


@dataclass
class StageResult:
    text: str
    session_id: str | None = None


def print_banner(stage: str, description: str, event_bus: EventBus | None = None) -> None:
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"  {stage}: {description}")
    print(f"{separator}\n")


async def run_stage(
    client: ClaudeSDKClient,
    stage: str,
    description: str,
    prompt: str,
    event_bus: EventBus | None = None,
) -> StageResult:
    """Send a prompt to the agent session, collect and return text output."""
    print_banner(stage, description)
    if event_bus:
        await event_bus.emit({"type": "banner", "data": {"stage": stage, "description": description}})

    await client.query(prompt)

    collected_text: list[str] = []
    session_id: str | None = None
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ThinkingBlock):
                    print(f"  [{stage}] thinking ({len(block.thinking)} chars)")
                    if event_bus:
                        await event_bus.emit({
                            "type": "thinking",
                            "data": {"stage": stage, "text": block.thinking},
                        })
                elif isinstance(block, TextBlock):
                    collected_text.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    # Include tool input for better UI display
                    tool_input = dict(block.input) if block.input else {}
                    # Sanitize input for display (truncate long values)
                    sanitized_input = {}
                    for k, v in tool_input.items():
                        v_str = str(v)
                        if len(v_str) > 100:
                            v_str = v_str[:97] + "..."
                        sanitized_input[k] = v_str
                    print(f"  [{stage}] tool: {block.name}")
                    if event_bus:
                        await event_bus.emit({
                            "type": "tool",
                            "data": {"stage": stage, "tool": block.name, "input": sanitized_input}
                        })
        elif isinstance(message, UserMessage):
            # UserMessage carries ToolResultBlock content from tool executions
            content = message.content if isinstance(message.content, list) else []
            for block in content:
                if isinstance(block, ToolResultBlock) and block.is_error:
                    snippet = str(block.content)[:200] if block.content else ""
                    print(f"  [{stage}] tool result ERROR: {snippet}")
                    if event_bus:
                        await event_bus.emit({
                            "type": "tool_error",
                            "data": {"stage": stage, "error": snippet},
                        })
        elif isinstance(message, ResultMessage):
            session_id = message.session_id
            cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
            duration = message.duration_ms
            turns = message.num_turns
            print(f"  [{stage}] turns={turns}  cost={cost}  duration={duration}ms")
            if event_bus:
                full_text = "\n".join(collected_text).strip()
                if full_text:
                    await event_bus.emit({
                        "type": "stage_text",
                        "data": {"stage": stage, "text": full_text},
                    })
                await event_bus.emit({
                    "type": "result",
                    "data": {"stage": stage, "turns": turns, "cost": cost, "duration": duration},
                })

    return StageResult(text="\n".join(collected_text), session_id=session_id)
