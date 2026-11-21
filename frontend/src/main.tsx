import "./index.css";

import { MotionConfig } from "framer-motion";
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { RouteErrorBoundary } from "./components/ErrorBoundary";
import { TooltipProvider } from "./components/Tooltip";
import { UiProvider } from "./components/ui-context";
import { startAccount } from "./lib/account";
import { useCalmFx } from "./lib/calm";
import { reloadOnce } from "./lib/chunkError";
import { initPointerGlow } from "./lib/pointerGlow";
import { registerServiceWorker } from "./lib/pwa";
import { ThemeProvider } from "./lib/theme";

/** Framer Motion folgt dem System oder „Effekte reduzieren“ (Konto). */
function FxConfig({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion={useCalmFx() ? "always" : "user"}>{children}</MotionConfig>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <FxConfig>
      <ThemeProvider>
        <TooltipProvider>
          <BrowserRouter>
            <UiProvider>
              <RouteErrorBoundary fullPage>
                <App />
              </RouteErrorBoundary>
            </UiProvider>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </FxConfig>
  </StrictMode>,
);

// Vite meldet fehlgeschlagene Chunk-Imports (alte Version nach Deploy): einmal neu laden.
window.addEventListener("vite:preloadError", (event) => {
  if (reloadOnce()) event.preventDefault();
});

initPointerGlow();
startAccount();
registerServiceWorker();
