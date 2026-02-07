from dotenv import load_dotenv

load_dotenv()

import asyncio
import json
import os

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

from events import EventBus
from run_pipeline import run_pipeline

HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")

# Global state
_status: dict = {"status": "idle", "stage": ""}
_bus: EventBus | None = None
_task: asyncio.Task | None = None
_history: list[dict] = []


async def _run(ticket: str, target: str) -> None:
    global _status, _bus, _task, _history
    _history = []
    _bus = EventBus()
    _status = {"status": "running", "stage": "INIT"}
    try:

        async def _track_and_record() -> None:
            """Background listener that updates _status and records history."""
            async for event in _bus.subscribe():
                _history.append(event)
                if event.get("type") == "banner":
                    _status["stage"] = event["data"]["stage"]

        tracker = asyncio.create_task(_track_and_record())

        report = await run_pipeline(ticket, target, event_bus=_bus)
        await _bus.emit({"type": "report", "data": {"text": report}})
        await _bus.emit({"type": "done", "data": {}})
        _status = {"status": "done", "stage": "DONE"}
        tracker.cancel()
    except Exception as exc:
        if _bus:
            await _bus.emit({"type": "error", "data": {"message": str(exc)}})
            await _bus.emit({"type": "done", "data": {}})
        _status = {"status": "idle", "stage": ""}
    finally:
        _task = None


async def homepage(request: Request) -> HTMLResponse:
    with open(HTML_PATH) as f:
        return HTMLResponse(f.read())


async def api_run(request: Request) -> JSONResponse:
    global _task
    if _task is not None and not _task.done():
        return JSONResponse({"error": "Pipeline already running"}, status_code=409)

    body = await request.json()
    ticket = body.get("ticket", "").strip()
    target = body.get("target", os.getcwd()).strip()
    if not ticket:
        return JSONResponse({"error": "ticket is required"}, status_code=400)

    _task = asyncio.create_task(_run(ticket, target))
    return JSONResponse({"ok": True})


async def api_events(request: Request) -> EventSourceResponse:
    async def generator():
        # Replay past events so refreshing clients catch up
        for event in list(_history):
            yield {"event": event.get("type", "log"), "data": json.dumps(event.get("data", {}))}
            if event.get("type") == "done":
                return

        # Stream live events if pipeline is still running
        if _bus is None:
            return
        async for event in _bus.subscribe():
            yield {"event": event.get("type", "log"), "data": json.dumps(event.get("data", {}))}
            if event.get("type") == "done":
                break

    return EventSourceResponse(generator())


async def api_status(request: Request) -> JSONResponse:
    return JSONResponse(_status)


async def api_config(request: Request) -> JSONResponse:
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    return JSONResponse({
        "default_target": cwd,
        "home": home,
        "common_dirs": [
            {"name": "Current", "path": cwd},
            {"name": "Parent", "path": os.path.dirname(cwd)},
            {"name": "Home", "path": home},
        ]
    })


async def api_list_dirs(request: Request) -> JSONResponse:
    """List directories at a given path (for directory browser)."""
    body = await request.json()
    path = body.get("path", os.getcwd())

    # Security: only allow listing subdirectories, resolve absolute path
    try:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return JSONResponse({"error": "Path does not exist"}, status_code=404)

        entries = []
        # Add parent directory (if not at root)
        parent = os.path.dirname(path)
        if parent != path:
            entries.append({"name": "..", "path": parent, "is_dir": True})

        # List directories
        for entry in os.scandir(path):
            if entry.is_dir():
                entries.append({"name": entry.name, "path": entry.path, "is_dir": True})

        return JSONResponse({"path": path, "entries": entries})
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, status_code=403)


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/api/run", api_run, methods=["POST"]),
        Route("/api/events", api_events),
        Route("/api/status", api_status),
        Route("/api/config", api_config),
        Route("/api/list_dirs", api_list_dirs, methods=["POST"]),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
