from dotenv import load_dotenv
import asyncio
import os
import sys

from run_pipeline import run_pipeline

load_dotenv()

TICKET_PATH = os.path.join(os.path.dirname(__file__), "ticket.md")
TARGET_APP = "/home/xh/testapp"


async def main() -> None:
    if not os.path.exists(TICKET_PATH):
        print(f"Error: {TICKET_PATH} not found. Create a ticket.md with your bug or feature description.")
        sys.exit(1)

    with open(TICKET_PATH) as f:
        ticket = f.read().strip()

    report = await run_pipeline(ticket, TARGET_APP)

    print("\n" + "=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)
    print(report)
    print("\ndone")


if __name__ == "__main__":
    asyncio.run(main())
