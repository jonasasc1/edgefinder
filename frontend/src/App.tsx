import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

import { AppShell } from "./components/AppShell";
import { OverviewPage } from "./pages/overview/OverviewPage";
import { AssetPlaceholder, PlaceholderPage } from "./pages/PlaceholderPage";

// Design-Seite mit Chart-Bibliothek erst bei Bedarf laden.
const DesignPage = lazy(() => import("./pages/DesignPage").then((m) => ({ default: m.DesignPage })));

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="makro" element={<PlaceholderPage title="Makro" text="Die Heatmap der Volkswirtschaften folgt in Etappe f." />} />
        <Route path="aenderungen" element={<PlaceholderPage title="Änderungen" text="Hier siehst du später, welche Scores sich seit gestern oder seit einer Woche am stärksten bewegt haben." />} />
        <Route path="favoriten" element={<PlaceholderPage title="Favoriten" text="Favoriten speicherst du später direkt im Browser; die Seite folgt in Etappe f." />} />
        <Route path="status" element={<PlaceholderPage title="Status" text="Die Aktualität der Datenquellen folgt in Etappe f." />} />
        <Route path="asset/:id" element={<AssetPlaceholder />} />
        <Route path="design" element={<Suspense fallback={null}><DesignPage /></Suspense>} />
        <Route path="*" element={<PlaceholderPage title="Nicht gefunden" text="Diese Adresse gibt es nicht. Wähle eine Seite in der Navigation." />} />
      </Route>
    </Routes>
  );
}
