"""
PoC: Does the Claude Agent SDK expose ThinkingBlock?
Run with: source .venv/bin/activate && python3 poc_thinking.py
"""
import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    UserMessage,
)

PROMPT = "What is 97 * 83? Think step by step before answering."


async def main() -> None:
    options = ClaudeAgentOptions(
        max_thinking_tokens=5000,
        max_turns=1,
        allowed_tools=[],  # no tools — pure reasoning
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(PROMPT)

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ThinkingBlock):
                        print("─" * 60)
                        print("🧠 THINKING BLOCK FOUND")
                        print("─" * 60)
                        print(block.thinking[:500])  # first 500 chars
                        print(f"  ... ({len(block.thinking)} chars total)")
                    elif isinstance(block, TextBlock):
                        print("─" * 60)
                        print("💬 TEXT BLOCK")
                        print("─" * 60)
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"🔧 TOOL: {block.name}")
                    else:
                        print(f"❓ UNKNOWN BLOCK TYPE: {type(block)}")

            elif isinstance(message, UserMessage):
                print(f"[UserMessage with {len(message.content)} blocks]")

            elif isinstance(message, ResultMessage):
                print("─" * 60)
                cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
                print(f"✅ Done  turns={message.num_turns}  cost={cost}  duration={message.duration_ms}ms")


asyncio.run(main())
