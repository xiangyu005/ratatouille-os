"""Pydantic request/response schemas — the CORE API contract surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=128)
    client: str = Field(default="unknown", max_length=32)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    request_id: str
    accepted: bool
    event_ids: list[int] = Field(default_factory=list)
    state_version: int
    error: ErrorDetail | None = None
    cached: bool = False


class SnapshotResponse(BaseModel):
    state: dict[str, Any]
    last_event_id: int
    state_version: int


class EventListResponse(BaseModel):
    events: list[dict[str, Any]]
    last_event_id: int


class TaskListResponse(BaseModel):
    tasks: list[dict[str, Any]]
    sim_time: int
    state_version: int


class ResourceResponse(BaseModel):
    workers: list[dict[str, Any]]
    stations: list[dict[str, Any]]
    sim_time: int
    state_version: int
