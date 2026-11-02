import { NavLink } from "react-router-dom";
import { PAGES, type PageMeta, SECTION_LABELS } from "../pages/pages";
import styles from "./shell.module.css";

const GROUP_ORDER: PageMeta["section"][] = ["game", "ai", "os", "food"];

export function NavRail() {
  return (
    <nav className={styles.nav} aria-label="頁面導航">
      {GROUP_ORDER.map((section) => {
        const pages = PAGES.filter((page) => page.section === section);
        return (
          <div key={section} className={styles.navGroup}>
            <h2 className={styles.navHeading}>{SECTION_LABELS[section]}</h2>
            <ul>
              {pages.map((page) => (
                <li key={page.path}>
                  <NavLink
                    to={page.path}
                    className={({ isActive }) => (isActive ? styles.navActive : styles.navLink)}
                    title={page.summary}
                  >
                    {page.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
