"""FastAPI application for the CORE service.

CORE is authoritative. FE and AI only reach the world through these routes.
The service starts and serves requests with both FE and AI stopped.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import core
from core.algorithms.scheduling import ALGORITHM_INFO, ASSIGNABLE
from core.api.schemas import (
    CommandRequest,
    CommandResponse,
    EventListResponse,
    ResourceResponse,
    SnapshotResponse,
    TaskListResponse,
)
from core.domain.errors import DomainError
from core.domain.models import Command, WorldState
from core.persistence.store import Store
from core.simulation.engine import WorldEngine


class EventHub:
    """Fan-out of committed events to connected WebSocket clients."""

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                # Slow client: drop its oldest event; it can resync via
                # GET /api/v1/events?after_id=... . Never block the world.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


def _db_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return Path(os.getenv("CORE_DB_PATH", "data/core/core.sqlite"))


def create_app(db_path: str | Path | None = None) -> FastAPI:
    store = Store(_db_path(str(db_path) if db_path else None))
    raw_state = store.load_latest_state()
    if raw_state is None:
        state = WorldState.new(seed=int(os.getenv("SIM_SEED", "42")))
    else:
        state = WorldState.from_dict(raw_state)

    engine = WorldEngine(state, store)
    hub = EventHub()

    docs_enabled = os.getenv("ENABLE_DOCS", "0") == "1"
    app = FastAPI(
        title="Ratatouille OS — CORE",
        version=core.__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.engine = engine
    app.state.store = store
    app.state.hub = hub

    origins = [
        origin.strip()
        for origin in os.getenv(
            "CORE_CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "core",
            "version": core.__version__,
            "sim_time": engine.state.sim_time,
            "state_version": engine.state.version,
        }

    @app.get("/api/v1/meta")
    def meta() -> dict[str, Any]:
        return {
            "service": "core",
            "version": core.__version__,
            "schema_version": store.schema_version(),
            "algorithms": ALGORITHM_INFO,
            "policies": sorted(ASSIGNABLE),
            "default_policy": engine.state.policy,
        }

    @app.get("/api/v1/snapshot", response_model=SnapshotResponse)
    def snapshot() -> dict[str, Any]:
        return engine.snapshot()

    @app.get("/api/v1/events", response_model=EventListResponse)
    def events(
        after_id: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        return {
            "events": store.get_events(after_id=after_id, limit=limit),
            "last_event_id": engine.state.last_event_id,
        }

    @app.get("/api/v1/tasks", response_model=TaskListResponse)
    def tasks() -> dict[str, Any]:
        return {
            "tasks": [
                task.to_dict()
                for task in sorted(engine.state.tasks.values(), key=lambda t: t.id)
            ],
            "sim_time": engine.state.sim_time,
            "state_version": engine.state.version,
        }

    @app.get("/api/v1/resources", response_model=ResourceResponse)
    def resources() -> dict[str, Any]:
        return {
            "workers": [
                worker.to_dict()
                for worker in sorted(engine.state.workers.values(), key=lambda w: w.id)
            ],
            "stations": [
                station.to_dict()
                for station in sorted(
                    engine.state.stations.values(), key=lambda s: s.id
                )
            ],
            "sim_time": engine.state.sim_time,
            "state_version": engine.state.version,
        }

    @app.post("/api/v1/commands", response_model=CommandResponse, status_code=202)
    async def command(request: Request, body: CommandRequest) -> dict[str, Any]:
        cmd = Command(
            command=body.command,
            args=body.args,
            idempotency_key=body.idempotency_key,
            client=body.client,
            request_id=request.state.request_id,
        )
        result, emitted = await engine.execute(cmd)
        if result.accepted:
            for event in emitted:
                await hub.publish(event.to_dict())
        return result.to_dict()

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "request_id": request_id,
                "accepted": False,
                "event_ids": [],
                "state_version": engine.state.version,
                "error": exc.to_dict(),
                "cached": False,
            },
        )

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = await hub.subscribe()
        try:
            await websocket.send_json(
                {
                    "type": "SNAPSHOT",
                    "state": engine.state.to_dict(),
                    "last_event_id": engine.state.last_event_id,
                    "state_version": engine.state.version,
                }
            )
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    await websocket.send_json(
                        {"type": "PING", "sim_time": engine.state.sim_time}
                    )
                    continue
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    return app
