import { type FormEvent, useState } from "react";
import type { CoreError } from "../api/client";
import {
  newIdempotencyKey,
  useMeta,
  useResources,
  useSendCommand,
  useSnapshot,
  useTasks,
} from "../api/queries";
import type { Station, Task, Worker, WorldState } from "../api/types";
import { LogStream } from "../components/LogStream";
import { EmptyState, ErrorBanner, Panel } from "../components/Panel";
import { useUiStore } from "../store/ui";
import styles from "./pages.module.css";

function asWorld(value: unknown): WorldState | undefined {
  return value as WorldState | undefined;
}

export default function GamePage() {
  const snapshot = useSnapshot();
  const tasks = useTasks();
  const resources = useResources();
  const meta = useMeta();
  const events = useUiStore((state) => state.events);
  const send = useSendCommand();

  const [name, setName] = useState("番茄湯-取料");
  const [burst, setBurst] = useState(4);
  const [priority, setPriority] = useState(0);
  const [policy, setPolicy] = useState("sjf");
  const [seconds, setSeconds] = useState(10);
  const [feedback, setFeedback] = useState<string | null>(null);

  const world = asWorld(snapshot.data?.state);
  const taskList = (tasks.data?.tasks ?? []) as unknown as Task[];
  const workers = (resources.data?.workers ?? []) as unknown as Worker[];
  const stations = (resources.data?.stations ?? []) as unknown as Station[];
  const policies = meta.data?.policies ?? ["fcfs", "sjf", "priority_aging"];

  const run = (command: string, args: Record<string, unknown>) => {
    setFeedback(null);
    send.mutate(
      { command, args, idempotency_key: newIdempotencyKey() },
      {
        onSuccess: (result) =>
          setFeedback(
            `accepted · events [${(result.event_ids ?? []).join(", ") || "—"}] · v${result.state_version}`,
          ),
        onError: (error) => setFeedback(`${(error as CoreError).code}: ${error.message}`),
      },
    );
  };

  const onEnqueue = (event: FormEvent) => {
    event.preventDefault();
    run("ENQUEUE_TASK", { name, burst_seconds: burst, priority });
  };

  const onAdvance = (event: FormEvent) => {
    event.preventDefault();
    run("ADVANCE_TIME", { seconds });
  };

  return (
    <div className={styles.page}>
      {snapshot.isError ? (
        <ErrorBanner
          message={`CORE 無法連線（${(snapshot.error as CoreError).message}）`}
          onRetry={() => void snapshot.refetch()}
        />
      ) : null}

      <div className={styles.grid}>
        <Panel
          title="世界狀態"
          actions={
            <button type="button" onClick={() => void snapshot.refetch()}>
              重新整理
            </button>
          }
        >
          {world ? (
            <dl className={styles.kv}>
              <dt>sim_time</dt>
              <dd>{world.sim_time}</dd>
              <dt>state_version</dt>
              <dd>{world.version}</dd>
              <dt>last_event_id</dt>
              <dd>{world.last_event_id}</dd>
              <dt>policy</dt>
              <dd>{world.policy}</dd>
              <dt>seed</dt>
              <dd>{world.seed}</dd>
              <dt>next_task_seq</dt>
              <dd>{world.next_task_seq}</dd>
            </dl>
          ) : (
            <EmptyState message={snapshot.isLoading ? "載入中…" : "沒有世界狀態"} />
          )}
        </Panel>

        <Panel title="資源">
          {workers.length === 0 && stations.length === 0 ? (
            <EmptyState message="載入中…" />
          ) : (
            <div className={styles.columns}>
              <ul className={styles.resourceList}>
                {workers.map((worker) => (
                  <li key={worker.id}>
                    <span>{worker.id}</span>
                    <span className={styles.dim}>{worker.task_id ?? "—"}</span>
                    <span className={worker.status === "busy" ? styles.busy : styles.free}>
                      {worker.status}
                    </span>
                  </li>
                ))}
              </ul>
              <ul className={styles.resourceList}>
                {stations.map((station) => (
                  <li key={station.id}>
                    <span>{station.id}</span>
                    <span className={styles.dim}>{station.name}</span>
                    <span className={station.status === "busy" ? styles.busy : styles.free}>
                      {station.status}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        <Panel title="任務" style={{ gridColumn: "span 2" }}>
          {taskList.length === 0 ? (
            <EmptyState message="目前沒有任務；用下面的指令建立一個。" />
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>task</th>
                  <th>名稱</th>
                  <th>狀態</th>
                  <th>burst</th>
                  <th>prio</th>
                  <th>worker</th>
                  <th>station</th>
                  <th>start</th>
                  <th>finish</th>
                </tr>
              </thead>
              <tbody>
                {taskList.map((task) => (
                  <tr key={task.id}>
                    <td>{task.id}</td>
                    <td>{task.name}</td>
                    <td className={task.status === "done" ? styles.free : styles.dim}>
                      {task.status}
                    </td>
                    <td>{task.burst_seconds}</td>
                    <td>{task.priority}</td>
                    <td>{task.worker_id ?? "—"}</td>
                    <td>{task.station_id ?? "—"}</td>
                    <td>{task.started_at ?? "—"}</td>
                    <td>{task.finished_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="送 command" style={{ gridColumn: "span 2" }}>
          <div className={styles.forms}>
            <form className={styles.form} onSubmit={onEnqueue}>
              <span className={styles.formTitle}>ENQUEUE_TASK</span>
              <label>
                名稱
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
              <label>
                burst
                <input
                  type="number"
                  min={1}
                  value={burst}
                  onChange={(event) => setBurst(Number(event.target.value))}
                />
              </label>
              <label>
                優先權
                <input
                  type="number"
                  value={priority}
                  onChange={(event) => setPriority(Number(event.target.value))}
                />
              </label>
              <button type="submit" disabled={send.isPending}>
                送出
              </button>
            </form>

            <form
              className={styles.form}
              onSubmit={(event) => {
                event.preventDefault();
                run("SCHEDULE_QUEUE", { policy });
              }}
            >
              <span className={styles.formTitle}>SCHEDULE_QUEUE</span>
              <label>
                策略
                <select value={policy} onChange={(event) => setPolicy(event.target.value)}>
                  {policies.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" disabled={send.isPending}>
                排程
              </button>
            </form>

            <form className={styles.form} onSubmit={onAdvance}>
              <span className={styles.formTitle}>ADVANCE_TIME</span>
              <label>
                秒數
                <input
                  type="number"
                  min={1}
                  value={seconds}
                  onChange={(event) => setSeconds(Number(event.target.value))}
                />
              </label>
              <button type="submit" disabled={send.isPending}>
                推進
              </button>
            </form>
          </div>
          {feedback ? (
            <p
              className={feedback.startsWith("accepted") ? styles.feedbackOk : styles.feedbackError}
            >
              {feedback}
            </p>
          ) : null}
          <p className={styles.dim}>
            FE 不自行改世界狀態；送出後等 CORE 回 202 與 WebSocket 事件（docs/22-01 §5.2）。
          </p>
        </Panel>

        <Panel title="事件流" scroll style={{ gridColumn: "span 2", height: 260 }}>
          <LogStream events={events} />
        </Panel>
      </div>
    </div>
  );
}
