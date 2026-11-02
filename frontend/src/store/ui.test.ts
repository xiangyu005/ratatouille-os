import { beforeEach, describe, expect, it } from "vitest";
import type { CoreEvent } from "../api/types";
import { EVENT_BUFFER_LIMIT, useUiStore } from "./ui";

function makeEvent(id: number, type = "TASK_ENQUEUED"): CoreEvent {
  return {
    event_id: id,
    type,
    sim_time: id,
    state_version: id,
    payload: {},
    causation_id: null,
    correlation_id: null,
  };
}

describe("ui store", () => {
  beforeEach(() => {
    useUiStore.setState({
      wsStatus: "connecting",
      lastEventId: 0,
      events: [],
      typeFilter: "",
    });
  });

  it("keeps events unique by event_id (reconnect catch-up may replay)", () => {
    const { pushEvent } = useUiStore.getState();
    pushEvent(makeEvent(1));
    pushEvent(makeEvent(1));
    pushEvent(makeEvent(2));

    const { events, lastEventId } = useUiStore.getState();
    expect(events.map((event) => event.event_id)).toEqual([1, 2]);
    expect(lastEventId).toBe(2);
  });

  it("caps the buffer at EVENT_BUFFER_LIMIT but keeps lastEventId", () => {
    const { pushEvent } = useUiStore.getState();
    for (let index = 1; index <= EVENT_BUFFER_LIMIT + 25; index += 1) {
      pushEvent(makeEvent(index));
    }

    const { events, lastEventId } = useUiStore.getState();
    expect(events).toHaveLength(EVENT_BUFFER_LIMIT);
    expect(events[0]?.event_id).toBe(26);
    expect(lastEventId).toBe(EVENT_BUFFER_LIMIT + 25);
  });

  it("never moves lastEventId backwards on a resync snapshot", () => {
    useUiStore.setState({ lastEventId: 40 });
    useUiStore.getState().applySnapshot(12);
    expect(useUiStore.getState().lastEventId).toBe(40);
  });
});
