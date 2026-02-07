from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from events import EventBus


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
) -> str:
    """Send a prompt to the agent session, collect and return text output."""
    print_banner(stage, description)
    if event_bus:
        await event_bus.emit({"type": "banner", "data": {"stage": stage, "description": description}})

    await client.query(prompt)

    collected_text: list[str] = []
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    collected_text.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"  [{stage}] tool: {block.name}")
                    if event_bus:
                        await event_bus.emit({"type": "tool", "data": {"stage": stage, "tool": block.name}})
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
            cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
            duration = message.duration_ms
            turns = message.num_turns
            print(f"  [{stage}] turns={turns}  cost={cost}  duration={duration}ms")
            if event_bus:
                await event_bus.emit({
                    "type": "result",
                    "data": {"stage": stage, "turns": turns, "cost": cost, "duration": duration},
                })

    return "\n".join(collected_text)
