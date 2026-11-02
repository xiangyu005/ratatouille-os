import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import type { CoreEvent } from "../api/types";
import { useUiStore } from "../store/ui";
import { LogStream } from "./LogStream";

function makeEvent(id: number, type: string): CoreEvent {
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

describe("LogStream", () => {
  beforeEach(() => {
    useUiStore.setState({ events: [], lastEventId: 0, typeFilter: "" });
  });

  it("shows an empty state when no event has arrived", () => {
    render(<LogStream events={[]} />);
    expect(screen.getByText("尚無事件")).toBeInTheDocument();
  });

  it("renders events and filters them by type", async () => {
    const user = userEvent.setup();
    const events = [makeEvent(1, "TASK_ENQUEUED"), makeEvent(2, "TIME_ADVANCED")];
    render(<LogStream events={events} />);

    const list = screen.getByRole("list");
    expect(within(list).getByText("TASK_ENQUEUED")).toBeInTheDocument();
    expect(within(list).getByText("TIME_ADVANCED")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("filter"), "TIME_ADVANCED");

    expect(within(list).queryByText("TASK_ENQUEUED")).not.toBeInTheDocument();
    expect(within(list).getByText("TIME_ADVANCED")).toBeInTheDocument();
  });
});
