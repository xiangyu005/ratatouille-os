/**
 * Shell smoke test: mount the real router against a stubbed CORE.
 *
 * This catches "white screen" regressions (bad provider wiring, a page that
 * throws on first render) without needing a browser. The real contract is
 * verified separately against a running CORE (`docs/24`).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const SNAPSHOT = {
  request_id: "req-1",
  state: {
    sim_time: 12,
    version: 3,
    seed: 42,
    policy: "sjf",
    next_task_seq: 2,
    last_event_id: 7,
    tasks: {
      "T-0001": {
        id: "T-0001",
        name: "番茄湯-取料",
        burst_seconds: 4,
        priority: 0,
        status: "queued",
        remaining_seconds: null,
        enqueued_at: 0,
        started_at: null,
        finished_at: null,
        worker_id: null,
        station_id: null,
      },
    },
    workers: { "W-1": { id: "W-1", name: "Worker 1", status: "idle", task_id: null } },
    stations: { "S-1": { id: "S-1", name: "Prep Station", status: "free", task_id: null } },
  },
  last_event_id: 7,
  state_version: 3,
};

const TASKS = {
  request_id: "req-2",
  tasks: Object.values(SNAPSHOT.state.tasks),
  sim_time: 12,
  state_version: 3,
};
const RESOURCES = {
  request_id: "req-3",
  workers: Object.values(SNAPSHOT.state.workers),
  stations: Object.values(SNAPSHOT.state.stations),
  sim_time: 12,
  state_version: 3,
};
const META = {
  request_id: "req-4",
  service: "core",
  version: "0.1.0",
  schema_version: 2,
  algorithms: [],
  policies: ["fcfs", "sjf"],
  default_policy: "sjf",
};
const HEALTH = { request_id: "req-5", status: "ok", sim_time: 12, state_version: 3 };

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const routes: Record<string, unknown> = {
  "/health": HEALTH,
  "/api/v1/meta": META,
  "/api/v1/snapshot": SNAPSHOT,
  "/api/v1/tasks": TASKS,
  "/api/v1/resources": RESOURCES,
};

class FakeSocket {
  static last: FakeSocket | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeSocket.last = this;
  }

  close() {}
}

async function renderShell() {
  const { AppShell } = await import("./shell/AppShell");
  const GamePage = (await import("./pages/GamePage")).default;
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AppShell />,
        children: [{ path: "game", element: <GamePage /> }],
      },
    ],
    { initialEntries: ["/game"] },
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("AppShell + GamePage", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeSocket as unknown as typeof WebSocket);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        const path = new URL(url).pathname;
        const body = routes[path];
        return body === undefined ? new Response("not found", { status: 404 }) : jsonResponse(body);
      }),
    );
  });

  it("renders the shell, the world state and the task table", async () => {
    await renderShell();

    expect(await screen.findByText("世界狀態")).toBeInTheDocument();
    expect(await screen.findByText("番茄湯-取料")).toBeInTheDocument();
    // sim_time appears in both the status bar and the world panel.
    expect(screen.getAllByText("sim_time").length).toBeGreaterThan(0);
    expect(screen.getAllByText("12").length).toBeGreaterThan(0);
    expect(screen.getByText("ENQUEUE_TASK")).toBeInTheDocument();
    expect(FakeSocket.last?.url).toContain("/ws/events");
  });
});
