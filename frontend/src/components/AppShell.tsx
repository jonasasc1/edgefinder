import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";

import { BackgroundFx } from "./fx/BackgroundFx";
import { Intro } from "./fx/Intro";
import { ZapEgg } from "./fx/ZapEgg";
import { ZapTransition } from "./fx/ZapTransition";
import { CommandPalette } from "./CommandPalette";
import { ExplainSheet } from "./ExplainSheet";
import { RouteErrorBoundary } from "./ErrorBoundary";
import { Footer } from "./Footer";
import { OfflineBanner } from "./OfflineBanner";
import { ShortcutsSheet } from "./ShortcutsSheet";
import { Sidebar } from "./Sidebar";
import { TabBar } from "./TabBar";
import { useUi } from "./ui-context";
import { useShortcuts } from "../lib/useShortcuts";

/** Rahmen: Sidebar (Desktop) oder Tab-Bar (Handy), dazwischen die Seite, darunter der Hinweis. */
export function AppShell() {
  const { pathname } = useLocation();
  const { paletteOpen, setPaletteOpen, setHelpOpen } = useUi();
  // Neue Seite = oben beginnen (kein Daten-Router, daher kein ScrollRestoration).
  // Block statt Pfeil-Ausdruck: neuere Browser geben von scrollTo ein Promise zurück, und React
  // behandelt jeden Rückgabewert eines Effekts als Aufräumfunktion („destroy is not a function“).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  useShortcuts({
    togglePalette: () => setPaletteOpen(!paletteOpen),
    openPalette: () => setPaletteOpen(true),
    openHelp: () => setHelpOpen(true),
  });
  return (
    <div className="min-h-dvh">
      <a
        href="#inhalt"
        className="sr-only z-50 rounded-control bg-surface px-4 py-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Zum Inhalt springen
      </a>
      <BackgroundFx />
      <Sidebar />
      <main id="inhalt" className="pb-[calc(var(--spacing-tabbar)+env(safe-area-inset-bottom)+1.5rem)] lg:pb-12 lg:pl-sidebar">
        <div className="mx-auto max-w-page">
          <OfflineBanner />
          <RouteErrorBoundary resetKey={pathname}>
            <Outlet />
          </RouteErrorBoundary>
          <Footer />
        </div>
      </main>
      <TabBar />
      <CommandPalette />
      <ShortcutsSheet />
      <ExplainSheet />
      <ZapTransition />
      <ZapEgg />
      <Intro />
    </div>
  );
}
