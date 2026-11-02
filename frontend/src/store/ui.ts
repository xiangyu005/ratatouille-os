/**
 * Client-only UI state (`docs/22-01` §5.1).
 *
 * The authoritative world never lives here: this store keeps the WebSocket
 * status, the event buffer for `LogStream`, and view filters.
 */

import { create } from "zustand";
import type { CoreEvent } from "../api/types";

export const EVENT_BUFFER_LIMIT = 500;

export type WsStatus = "connecting" | "open" | "closed" | "error";

interface UiState {
  wsStatus: WsStatus;
  lastEventId: number;
  events: CoreEvent[];
  typeFilter: string;
  setWsStatus: (status: WsStatus) => void;
  pushEvent: (event: CoreEvent) => void;
  applySnapshot: (lastEventId: number) => void;
  setTypeFilter: (filter: string) => void;
  clearEvents: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  wsStatus: "connecting",
  lastEventId: 0,
  events: [],
  typeFilter: "",

  setWsStatus: (wsStatus) => set({ wsStatus }),

  pushEvent: (event) =>
    set((state) => {
      // Reconnect catch-up can replay events; keep the buffer unique by id.
      if (state.events.some((existing) => existing.event_id === event.event_id)) {
        return state;
      }
      const events = [...state.events, event];
      return {
        events: events.length > EVENT_BUFFER_LIMIT ? events.slice(-EVENT_BUFFER_LIMIT) : events,
        lastEventId: Math.max(state.lastEventId, event.event_id),
      };
    }),

  applySnapshot: (lastEventId) =>
    set((state) => ({ lastEventId: Math.max(state.lastEventId, lastEventId) })),

  setTypeFilter: (typeFilter) => set({ typeFilter }),

  clearEvents: () => set({ events: [] }),
}));
