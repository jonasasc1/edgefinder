import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

import { AppShell } from "./components/AppShell";
import { BoltLoader } from "./components/fx/BoltLoader";
import { NotFound } from "./pages/asset/NotFound";
import { ChangesPage } from "./pages/changes/ChangesPage";
import { FavoritesPage } from "./pages/favorites/FavoritesPage";
import { MacroPage } from "./pages/macro/MacroPage";
import { OverviewPage } from "./pages/overview/OverviewPage";
import { StatusPage } from "./pages/status/StatusPage";

// Seiten mit Diagrammen erst bei Bedarf laden (hält das erste Bundle klein).
const AssetPage = lazy(() => import("./pages/asset/AssetPage").then((m) => ({ default: m.AssetPage })));
const ComparePage = lazy(() => import("./pages/compare/ComparePage").then((m) => ({ default: m.ComparePage })));
const later = (node: React.ReactNode) => <Suspense fallback={<BoltLoader />}>{node}</Suspense>;

// Design-Seite erst bei Bedarf laden.
const DesignPage = lazy(() => import("./pages/DesignPage").then((m) => ({ default: m.DesignPage })));

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="makro" element={<MacroPage />} />
        <Route path="aenderungen" element={<ChangesPage />} />
        <Route path="favoriten" element={<FavoritesPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="vergleich" element={later(<ComparePage />)} />
        <Route path="asset/:id" element={later(<AssetPage />)} />
        <Route path="design" element={<Suspense fallback={<BoltLoader />}><DesignPage /></Suspense>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
