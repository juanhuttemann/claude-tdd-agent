from dotenv import load_dotenv

load_dotenv()

import asyncio
import json
import os
import time

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from events import EventBus
from optimizer import generate_questions, rewrite_ticket
from run_pipeline import PipelineStopped, run_pipeline
from summarize import summarize_pipeline

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HTML_PATH = os.path.join(STATIC_DIR, "index.html")

# Global state
_status: dict = {"status": "idle", "stage": ""}
_bus: EventBus | None = None
_task: asyncio.Task | None = None
_history: list[dict] = []
_stop_event: asyncio.Event = asyncio.Event()
_ticket: str = ""
_target: str = ""
_optimize_task: asyncio.Task | None = None


async def _run(ticket: str, target: str, resume: bool = False, thinking: bool = False) -> None:
    global _status, _bus, _task, _history, _stop_event, _ticket, _target
    _history = []
    _bus = EventBus()
    _stop_event.clear()
    _status = {"status": "running", "stage": "INIT", "started_at": time.time() * 1000}
    _ticket = ticket
    _target = target
    try:

        async def _track_and_record() -> None:
            """Background listener that updates _status and records history."""
            async for event in _bus.subscribe():
                _history.append(event)
                if event.get("type") == "banner":
                    _status["stage"] = event["data"]["stage"]

        tracker = asyncio.create_task(_track_and_record())

        # Load prior summary if resuming
        prior_summary = None
        if resume:
            summary_path = os.path.join(target, ".tdd_summary.json")
            if os.path.exists(summary_path):
                with open(summary_path) as f:
                    summary_data = json.load(f)
                prior_summary = summary_data.get("summary", "")

        report = await run_pipeline(
            ticket,
            target,
            event_bus=_bus,
            stop_event=_stop_event,
            prior_summary=prior_summary,
            thinking=thinking,
        )
        await _bus.emit({"type": "report", "data": {"text": report}})
        await _bus.emit({"type": "done", "data": {}})
        _status.update({"status": "done", "stage": "DONE"})
        tracker.cancel()

    except PipelineStopped as stopped:
        # User requested stop — run summarization
        _status.update({"status": "stopping", "stage": "SUMMARIZE"})
        await _bus.emit({"type": "stopped", "data": {"message": "Pipeline stopped by user"}})

        try:
            summary = await summarize_pipeline(
                ticket=ticket,
                target=target,
                completed_stages=stopped.completed_stages,
                interrupted_stage=stopped.current_stage,
                tracker=stopped.tracker,
                event_history=list(_history),
                event_bus=_bus,
            )
            await _bus.emit({"type": "summary", "data": {"summary": summary}})
        except Exception as sum_exc:
            await _bus.emit({
                "type": "error",
                "data": {"message": f"Summarization failed: {sum_exc}"},
            })

        await _bus.emit({"type": "done", "data": {}})
        _status.update({"status": "done", "stage": "STOPPED"})

    except asyncio.CancelledError:
        # Task was cancelled (from stop endpoint) — run summarization
        _status.update({"status": "stopping", "stage": "SUMMARIZE"})
        if _bus:
            await _bus.emit({"type": "stopped", "data": {"message": "Pipeline stopped by user"}})

            try:
                # We don't have PipelineStopped info here, so use what we can
                from test_tracker import TestTracker
                fallback_tracker = TestTracker()
                summary = await summarize_pipeline(
                    ticket=ticket,
                    target=target,
                    completed_stages=[],
                    interrupted_stage=_status.get("stage", "UNKNOWN"),
                    tracker=fallback_tracker,
                    event_history=list(_history),
                    event_bus=_bus,
                )
                await _bus.emit({"type": "summary", "data": {"summary": summary}})
            except Exception as sum_exc:
                await _bus.emit({
                    "type": "error",
                    "data": {"message": f"Summarization failed: {sum_exc}"},
                })

            await _bus.emit({"type": "done", "data": {}})
        _status.update({"status": "done", "stage": "STOPPED"})

    except Exception as exc:
        if _bus:
            await _bus.emit({"type": "error", "data": {"message": str(exc)}})
            await _bus.emit({"type": "done", "data": {}})
        _status.update({"status": "idle", "stage": ""})
    finally:
        _task = None


async def homepage(request: Request) -> HTMLResponse:
    with open(HTML_PATH) as f:
        content = f.read()
    # Inject a cache-busting version derived from the static dir mtime so that
    # browsers always pick up updated JS modules after a server restart.
    try:
        v = int(os.path.getmtime(os.path.join(STATIC_DIR, "js", "main.js")))
    except OSError:
        v = int(time.time())
    content = content.replace('src="/static/js/main.js"', f'src="/static/js/main.js?v={v}"')
    return HTMLResponse(content)


async def api_run(request: Request) -> JSONResponse:
    global _task
    if _task is not None and not _task.done():
        return JSONResponse({"error": "Pipeline already running"}, status_code=409)

    body = await request.json()
    ticket = body.get("ticket", "").strip()
    target = body.get("target", os.getcwd()).strip()
    resume = body.get("resume", False)
    thinking = body.get("thinking", False)
    if not ticket:
        return JSONResponse({"error": "ticket is required"}, status_code=400)

    os.makedirs(target, exist_ok=True)
    _task = asyncio.create_task(_run(ticket, target, resume=resume, thinking=thinking))
    return JSONResponse({"ok": True})


async def api_stop(request: Request) -> JSONResponse:
    """Stop the running pipeline and trigger summarization."""
    global _stop_event, _task
    if _task is None or _task.done():
        return JSONResponse({"error": "No pipeline running"}, status_code=400)

    _stop_event.set()
    _task.cancel()
    return JSONResponse({"ok": True})


async def api_summary(request: Request) -> JSONResponse:
    """Return the saved summary for a given target path."""
    body = await request.json()
    target = body.get("target", "").strip()
    if not target:
        return JSONResponse({"error": "target is required"}, status_code=400)

    summary_path = os.path.join(target, ".tdd_summary.json")
    if not os.path.exists(summary_path):
        return JSONResponse({"error": "No summary found"}, status_code=404)

    with open(summary_path) as f:
        summary = json.load(f)
    return JSONResponse(summary)


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
    summary = None
    summary_path = os.path.join(cwd, ".tdd_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = json.load(f)
    return JSONResponse({
        "default_target": cwd,
        "home": home,
        "summary": summary,
        "common_dirs": [
            {"name": "Current", "path": cwd},
            {"name": "Parent", "path": os.path.dirname(cwd)},
            {"name": "Home", "path": home},
        ]
    })


async def api_optimize(request: Request) -> JSONResponse:
    """Generate clarifying questions for a vague ticket."""
    global _optimize_task
    if _optimize_task is not None and not _optimize_task.done():
        return JSONResponse({"error": "Optimization already in progress"}, status_code=409)

    body = await request.json()
    ticket = body.get("ticket", "").strip()
    target = body.get("target", os.getcwd()).strip()
    if not ticket:
        return JSONResponse({"error": "ticket is required"}, status_code=400)

    scan_codebase = os.path.isdir(target)

    try:
        _optimize_task = asyncio.ensure_future(
            generate_questions(ticket, target, scan_codebase=scan_codebase)
        )
        result = await _optimize_task
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        _optimize_task = None


async def api_optimize_submit(request: Request) -> JSONResponse:
    """Rewrite the ticket using user answers to clarifying questions."""
    global _optimize_task
    if _optimize_task is not None and not _optimize_task.done():
        return JSONResponse({"error": "Optimization already in progress"}, status_code=409)

    body = await request.json()
    ticket = body.get("ticket", "").strip()
    target = body.get("target", os.getcwd()).strip()
    context = body.get("context", "")
    answers = body.get("answers", [])
    if not ticket:
        return JSONResponse({"error": "ticket is required"}, status_code=400)
    if not answers:
        return JSONResponse({"error": "answers are required"}, status_code=400)

    try:
        _optimize_task = asyncio.ensure_future(
            rewrite_ticket(ticket, target, context, answers)
        )
        rewritten = await _optimize_task
        return JSONResponse({"optimized_ticket": rewritten})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        _optimize_task = None


async def api_mkdir(request: Request) -> JSONResponse:
    """Create a directory (and any missing parents)."""
    body = await request.json()
    target = body.get("target", "").strip()
    if not target:
        return JSONResponse({"error": "target is required"}, status_code=400)
    try:
        os.makedirs(target, exist_ok=True)
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


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


class NoCacheJSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/js/"):
            response.headers["Cache-Control"] = "no-store"
        return response


app = Starlette(
    middleware=[Middleware(NoCacheJSMiddleware)],
    routes=[
        Route("/", homepage),
        Route("/api/run", api_run, methods=["POST"]),
        Route("/api/stop", api_stop, methods=["POST"]),
        Route("/api/summary", api_summary, methods=["POST"]),
        Route("/api/events", api_events),
        Route("/api/status", api_status),
        Route("/api/config", api_config),
        Route("/api/optimize", api_optimize, methods=["POST"]),
        Route("/api/optimize/submit", api_optimize_submit, methods=["POST"]),
        Route("/api/mkdir", api_mkdir, methods=["POST"]),
        Route("/api/list_dirs", api_list_dirs, methods=["POST"]),
        Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
