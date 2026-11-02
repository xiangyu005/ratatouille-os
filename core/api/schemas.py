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
    request_id: str
    state: dict[str, Any]
    last_event_id: int
    state_version: int
    events: list[dict[str, Any]] | None = None


class EventListResponse(BaseModel):
    request_id: str
    events: list[dict[str, Any]]
    last_event_id: int


class TaskListResponse(BaseModel):
    request_id: str
    tasks: list[dict[str, Any]]
    sim_time: int
    state_version: int


class ResourceResponse(BaseModel):
    request_id: str
    workers: list[dict[str, Any]]
    stations: list[dict[str, Any]]
    sim_time: int
    state_version: int


class SaveRequest(BaseModel):
    label: str | None = Field(default=None, max_length=64)


class SaveResponse(BaseModel):
    request_id: str
    save_id: int
    schema_version: int
    state_version: int
    last_event_id: int
    label: str | None = None
    checksum: str
    created_at: str


class SaveListResponse(BaseModel):
    request_id: str
    saves: list[dict[str, Any]]


class LoadRequest(BaseModel):
    save_id: int | None = Field(default=None, ge=1)


class LoadResponse(BaseModel):
    request_id: str
    loaded: bool
    save_id: int
    state_version: int
    last_event_id: int
    label: str | None = None
