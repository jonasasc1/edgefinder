import "./index.css";

import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { RouteErrorBoundary } from "./components/ErrorBoundary";
import { TooltipProvider } from "./components/Tooltip";
import { UiProvider } from "./components/ui-context";
import { reloadOnce } from "./lib/chunkError";
import { initPointerGlow } from "./lib/pointerGlow";
import { registerServiceWorker } from "./lib/pwa";
import { ThemeProvider } from "./lib/theme";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
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
    </MotionConfig>
  </StrictMode>,
);

// Vite meldet fehlgeschlagene Chunk-Imports (alte Version nach Deploy): einmal neu laden.
window.addEventListener("vite:preloadError", (event) => {
  if (reloadOnce()) event.preventDefault();
});

initPointerGlow();
registerServiceWorker();
