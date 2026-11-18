import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import type { TermKey } from "../lib/glossary";

// Gemeinsamer Zustand der Oberfläche: Command-Palette, Tastenkürzel-Hilfe, Erklär-Sheet.
type UiContextValue = {
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  helpOpen: boolean;
  setHelpOpen: (open: boolean) => void;
  term: TermKey | null;
  explain: (term: TermKey | null) => void;
};

const UiContext = createContext<UiContextValue | null>(null);

export function UiProvider({ children }: { children: ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [term, setTerm] = useState<TermKey | null>(null);
  const explain = useCallback((next: TermKey | null) => setTerm(next), []);
  const value = useMemo(
    () => ({ paletteOpen, setPaletteOpen, helpOpen, setHelpOpen, term, explain }),
    [paletteOpen, helpOpen, term, explain],
  );
  return <UiContext.Provider value={value}>{children}</UiContext.Provider>;
}

export function useUi(): UiContextValue {
  const context = useContext(UiContext);
  if (!context) throw new Error("useUi braucht den UiProvider");
  return context;
}
