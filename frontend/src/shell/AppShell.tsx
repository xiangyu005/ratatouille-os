import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { useCoreSocket } from "../api/socket";
import { Panel } from "../components/Panel";
import { useUiStore } from "../store/ui";
import { NavRail } from "./NavRail";
import { StatusBar } from "./StatusBar";
import styles from "./shell.module.css";

function Footer() {
  const wsStatus = useUiStore((state) => state.wsStatus);
  const lastEventId = useUiStore((state) => state.lastEventId);
  return (
    <footer className={styles.footer}>
      <span>F1 Help</span>
      <span>F2 Jobs</span>
      <span>Ctrl+K Commands</span>
      <span className={styles.footerSpacer} />
      <span className={styles.dim}>ws {wsStatus}</span>
      <span className={styles.dim}>last_event {lastEventId}</span>
    </footer>
  );
}

export function AppShell() {
  // One socket for the whole shell; pages read the buffer from the store.
  useCoreSocket();

  return (
    <div className={styles.shell}>
      <StatusBar />
      <div className={styles.body}>
        <NavRail />
        <main className={styles.content}>
          <Suspense
            fallback={
              <Panel title="loading">
                <p className={styles.dim}>載入頁面…</p>
              </Panel>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
      <Footer />
    </div>
  );
}
