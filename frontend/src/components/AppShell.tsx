import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";

import { Sidebar } from "./Sidebar";
import { TabBar } from "./TabBar";

/** Rahmen: Sidebar (Desktop) oder Tab-Bar (Handy), dazwischen die Seite. */
export function AppShell() {
  const { pathname } = useLocation();
  // Neue Seite = oben beginnen (kein Daten-Router, daher kein ScrollRestoration).
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return (
    <div className="min-h-dvh">
      <a
        href="#inhalt"
        className="sr-only z-50 rounded-control bg-surface px-4 py-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Zum Inhalt springen
      </a>
      <Sidebar />
      <main id="inhalt" className="pb-[calc(var(--spacing-tabbar)+env(safe-area-inset-bottom)+1.5rem)] lg:pb-12 lg:pl-sidebar">
        <div className="mx-auto max-w-page">
          <Outlet />
        </div>
      </main>
      <TabBar />
    </div>
  );
}
