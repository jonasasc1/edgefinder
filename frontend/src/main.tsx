import "./index.css";

import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { TooltipProvider } from "./components/Tooltip";
import { UiProvider } from "./components/ui-context";
import { registerServiceWorker } from "./lib/pwa";
import { ThemeProvider } from "./lib/theme";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <TooltipProvider>
          <BrowserRouter>
            <UiProvider>
              <App />
            </UiProvider>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
);

registerServiceWorker();
