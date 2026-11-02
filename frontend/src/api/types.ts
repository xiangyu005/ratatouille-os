/**
 * WebSocket and world-state types.
 *
 * `docs/22-01` §7.1: WebSocket messages are not part of OpenAPI, so they live
 * here as a discriminated union whose fields mirror CORE's event envelope
 * (`docs/22` §5).
 */

export interface Task {
  id: string;
  name: string;
  burst_seconds: number;
  priority: number;
  status: string;
  remaining_seconds: number | null;
  enqueued_at: number;
  started_at: number | null;
  finished_at: number | null;
  worker_id: string | null;
  station_id: string | null;
}

export interface Worker {
  id: string;
  name: string;
  status: string;
  task_id: string | null;
}

export interface Station {
  id: string;
  name: string;
  status: string;
  task_id: string | null;
}

export interface WorldState {
  sim_time: number;
  version: number;
  seed: number;
  policy: string;
  next_task_seq: number;
  last_event_id: number;
  tasks: Record<string, Task>;
  workers: Record<string, Worker>;
  stations: Record<string, Station>;
}

export interface CoreEvent {
  event_id: number;
  type: string;
  sim_time: number;
  state_version: number;
  payload: Record<string, unknown>;
  causation_id: string | null;
  correlation_id: string | null;
  created_at?: string;
}

export interface SnapshotMessage {
  type: "SNAPSHOT";
  reason?: string;
  state: WorldState;
  last_event_id: number;
  state_version: number;
}

export interface PingMessage {
  type: "PING";
  sim_time: number;
}

export type SocketMessage = SnapshotMessage | PingMessage | CoreEvent;

export function isSnapshotMessage(message: SocketMessage): message is SnapshotMessage {
  return message.type === "SNAPSHOT" && "state" in message;
}

export function isCoreEvent(message: SocketMessage): message is CoreEvent {
  return typeof (message as CoreEvent).event_id === "number";
}
