import asyncio
from typing import Any, AsyncGenerator


class EventBus:
    """Async pub/sub event bus for streaming pipeline events to SSE clients."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    async def emit(self, event: dict[str, Any]) -> None:
        for queue in self._subscribers:
            await queue.put(event)

    async def subscribe(self) -> AsyncGenerator[dict[str, Any], None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("type") == "done":
                    break
        finally:
            self._subscribers.remove(queue)
