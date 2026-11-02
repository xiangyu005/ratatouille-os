/**
 * Event log view for the WebSocket stream.
 *
 * Kept dumb on purpose: filtering and the 500-event buffer live in the UI
 * store so this component stays testable without a socket.
 */

import { useEffect, useRef } from "react";
import type { CoreEvent } from "../api/types";
import { useUiStore } from "../store/ui";
import styles from "./components.module.css";

export function LogStream({ events }: { events: CoreEvent[] }) {
  const typeFilter = useUiStore((state) => state.typeFilter);
  const setTypeFilter = useUiStore((state) => state.setTypeFilter);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  const visible = typeFilter ? events.filter((event) => event.type === typeFilter) : events;
  const types = [...new Set(events.map((event) => event.type))].sort();

  // Auto-scroll unless the operator has scrolled up to read history.
  // biome-ignore lint/correctness/useExhaustiveDependencies: the ref is stable; we re-run when the list grows.
  useEffect(() => {
    const element = bodyRef.current;
    if (!element) {
      return;
    }
    const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
    if (nearBottom) {
      element.scrollTop = element.scrollHeight;
    }
  }, [visible.length]);

  return (
    <div className={styles.log}>
      <div className={styles.logToolbar}>
        <label htmlFor="event-filter">filter</label>
        <select
          id="event-filter"
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value)}
        >
          <option value="">all types</option>
          {types.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <span className={styles.dim}>
          {visible.length} / {events.length}
        </span>
      </div>
      <div className={styles.logBody} ref={bodyRef}>
        {visible.length === 0 ? (
          <p className={styles.empty}>尚無事件</p>
        ) : (
          <ol className={styles.logList}>
            {visible.map((event) => (
              <li key={event.event_id}>
                <span className={styles.dim}>{String(event.event_id).padStart(5, "0")}</span>
                <span className={styles.logType}>{event.type}</span>
                <span className={styles.dim}>t={event.sim_time}</span>
                <span className={styles.dim}>v={event.state_version}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
