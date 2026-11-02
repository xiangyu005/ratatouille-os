import { useQuery } from "@tanstack/react-query";
import { core, unwrap } from "../api/client";
import { useMeta, useSnapshot } from "../api/queries";
import { StatusDot } from "../components/Panel";
import styles from "./shell.module.css";

interface Health {
  status: string;
  sim_time: number;
  state_version: number;
}

async function getHealth(): Promise<Health> {
  return unwrap<Health>(await core.GET("/health"));
}

export function StatusBar() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15_000,
  });
  const snapshot = useSnapshot();
  const meta = useMeta();

  const coreStatus = health.isError ? "error" : health.data ? "ok" : "offline";
  const stateVersion = snapshot.data?.state_version ?? health.data?.state_version ?? "—";
  const simTime = snapshot.data?.state?.sim_time ?? health.data?.sim_time ?? "—";
  const policy = meta.data?.default_policy ?? "—";

  return (
    <header className={styles.statusBar}>
      <div className={styles.brand}>{"鼠於我的小餐館 // CORE"}</div>
      <div className={styles.statusGroup}>
        <StatusDot status={coreStatus} label={`CORE ${coreStatus === "ok" ? "ok" : "down"}`} />
        <StatusDot status="offline" label="AI" />
        <StatusDot status="offline" label="MCP" />
        <StatusDot status="offline" label="LOCAL" />
        <StatusDot status="offline" label="CLOUD" />
      </div>
      <div className={styles.metrics}>
        <span>
          sim_time <strong>{String(simTime)}</strong>
        </span>
        <span>
          v_state <strong>{String(stateVersion)}</strong>
        </span>
        <span>
          policy <strong>{policy}</strong>
        </span>
        <span className={styles.dim}>schema {meta.data?.schema_version ?? "—"}</span>
      </div>
    </header>
  );
}
