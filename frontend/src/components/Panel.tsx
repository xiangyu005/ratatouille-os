import type { CSSProperties, ReactNode } from "react";
import styles from "./components.module.css";

export type DotStatus = "ok" | "warn" | "error" | "offline";

export function StatusDot({ status, label }: { status: DotStatus; label?: string }) {
  return (
    <span className={styles.status} title={label ?? status}>
      <span className={`${styles.dot} ${styles[status]}`} aria-hidden="true" />
      {label ? <span className={styles.statusLabel}>{label}</span> : null}
    </span>
  );
}

interface PanelProps {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  scroll?: boolean;
  style?: CSSProperties;
}

export function Panel({ title, actions, children, scroll = false, style }: PanelProps) {
  return (
    <section className={styles.panel} style={style}>
      <header className={styles.panelHeader}>
        <h2>{title}</h2>
        {actions ? <div className={styles.panelActions}>{actions}</div> : null}
      </header>
      <div className={scroll ? styles.panelBodyScroll : styles.panelBody}>{children}</div>
    </section>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className={styles.empty}>{message}</p>;
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className={styles.errorBanner} role="alert">
      <span>{message}</span>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          重試
        </button>
      ) : null}
    </div>
  );
}
