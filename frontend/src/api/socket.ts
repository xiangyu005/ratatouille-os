/**
 * The single WebSocket to CORE (`docs/22-01` §5.2).
 *
 * - SNAPSHOT resyncs: it carries `last_event_id`, which replaces `state_version`
 *   guessing.
 * - Events land in the UI buffer and debounce a query invalidation, so panels
 *   refresh once per burst instead of once per event.
 * - Reconnects back off exponentially; a reconnect re-receives SNAPSHOT, so the
 *   buffer can be reconciled by `event_id`.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useUiStore } from "../store/ui";
import { CORE_WS } from "./client";
import { isCoreEvent, isSnapshotMessage, type SocketMessage } from "./types";

const INITIAL_RETRY_MS = 500;
const MAX_RETRY_MS = 10_000;
const INVALIDATE_DEBOUNCE_MS = 150;

export function useCoreSocket(): void {
  const queryClient = useQueryClient();
  const setWsStatus = useUiStore((state) => state.setWsStatus);
  const pushEvent = useUiStore((state) => state.pushEvent);
  const applySnapshot = useUiStore((state) => state.applySnapshot);

  const retryTimer = useRef<number | null>(null);
  const invalidateTimer = useRef<number | null>(null);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let retryDelay = INITIAL_RETRY_MS;

    const invalidateSoon = () => {
      if (invalidateTimer.current !== null) {
        window.clearTimeout(invalidateTimer.current);
      }
      invalidateTimer.current = window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: ["snapshot"] });
        void queryClient.invalidateQueries({ queryKey: ["tasks"] });
        void queryClient.invalidateQueries({ queryKey: ["resources"] });
      }, INVALIDATE_DEBOUNCE_MS);
    };

    const connect = () => {
      setWsStatus("connecting");
      socket = new WebSocket(CORE_WS);

      socket.onopen = () => {
        retryDelay = INITIAL_RETRY_MS;
        setWsStatus("open");
      };

      socket.onmessage = (raw) => {
        const message = JSON.parse(String(raw.data)) as SocketMessage;
        if (isSnapshotMessage(message)) {
          applySnapshot(message.last_event_id);
          invalidateSoon();
          return;
        }
        if (isCoreEvent(message)) {
          pushEvent(message);
          invalidateSoon();
        }
        // PING carries no state; it only keeps the connection observably alive.
      };

      socket.onerror = () => setWsStatus("error");

      socket.onclose = () => {
        if (disposed) {
          return;
        }
        setWsStatus("closed");
        retryTimer.current = window.setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_RETRY_MS);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer.current !== null) {
        window.clearTimeout(retryTimer.current);
      }
      if (invalidateTimer.current !== null) {
        window.clearTimeout(invalidateTimer.current);
      }
      socket?.close();
    };
  }, [applySnapshot, pushEvent, queryClient, setWsStatus]);
}
