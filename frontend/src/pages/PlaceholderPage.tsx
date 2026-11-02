import { EmptyState, Panel } from "../components/Panel";
import type { PageMeta } from "./pages";
import styles from "./pages.module.css";

export default function PlaceholderPage({ meta }: { meta: PageMeta }) {
  return (
    <div className={styles.page}>
      <Panel title={`${meta.label} // ${meta.section.toUpperCase()}`}>
        <dl className={styles.kv}>
          <dt>用途</dt>
          <dd>{meta.summary}</dd>
          <dt>依據</dt>
          <dd>{meta.doc}</dd>
          <dt>端點</dt>
          <dd>{meta.endpoints.length > 0 ? meta.endpoints.join("、") : "尚未定案"}</dd>
        </dl>
        <EmptyState message="此頁尚未實作：先立 route 與 shell 位置，等對應規格定案再填操作／過程／結果／圖表。" />
      </Panel>
    </div>
  );
}
