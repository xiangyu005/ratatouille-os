import { lazy } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import PlaceholderPage from "./pages/PlaceholderPage";
import { PAGES } from "./pages/pages";
import { AppShell } from "./shell/AppShell";

// Route-level code split: the shell stays small, pages load on demand
// (`docs/22-01` §9).
const GamePage = lazy(() => import("./pages/GamePage"));

const placeholderRoutes = PAGES.filter((page) => page.path !== "/game").map((page) => ({
  path: page.path.replace(/^\//, ""),
  element: <PlaceholderPage meta={page} />,
}));

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/game" replace /> },
      { path: "game", element: <GamePage /> },
      ...placeholderRoutes,
      { path: "*", element: <Navigate to="/game" replace /> },
    ],
  },
]);
