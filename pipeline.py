from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)


def print_banner(stage: str, description: str) -> None:
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"  {stage}: {description}")
    print(f"{separator}\n")


async def run_stage(
    client: ClaudeSDKClient,
    stage: str,
    description: str,
    prompt: str,
) -> str:
    """Send a prompt to the agent session, collect and return text output."""
    print_banner(stage, description)
    await client.query(prompt)

    collected_text: list[str] = []
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    collected_text.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"  [{stage}] tool: {block.name}")
        elif isinstance(message, ResultMessage):
            cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
            print(f"  [{stage}] turns={message.num_turns}  cost={cost}  duration={message.duration_ms}ms")

    return "\n".join(collected_text)
