import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useCalmFx } from "./calm";
import { storeValue, usePersistedValue } from "./usePersistentState";

export type ThemePref = "system" | "light" | "dark";
export type Resolved = "light" | "dark";

const KEY = "ef-theme";
const query = "(prefers-color-scheme: dark)";

type ThemeContextValue = { pref: ThemePref; resolved: Resolved; setPref: (pref: ThemePref) => void };

const ThemeContext = createContext<ThemeContextValue | null>(null);

export const THEME_KEY = KEY;

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Wahl aus dem gemeinsamen Speicher (lokal oder vom Konto); „system“ = kein Eintrag.
  const stored = usePersistedValue(KEY);
  const pref: ThemePref = stored === "light" || stored === "dark" ? stored : "system";
  const calm = useCalmFx();
  const [systemDark, setSystemDark] = useState(() => matchMedia(query).matches);

  useEffect(() => {
    const media = matchMedia(query);
    const onChange = () => setSystemDark(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const resolved: Resolved = pref === "system" ? (systemDark ? "dark" : "light") : pref;

  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
    // Statusleiste/Adressleiste folgen der Wahl (nicht nur dem System): ein Eintrag ohne media-Bedingung.
    const canvas = getComputedStyle(document.documentElement).getPropertyValue("--c-canvas").trim();
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => meta.remove());
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = canvas;
    document.head.append(meta);
  }, [resolved]);

  useEffect(() => {
    // Reduzierte Effekte: CSS (design/fx.css) folgt dem Attribut wie prefers-reduced-motion.
    if (calm) document.documentElement.dataset.calm = "1";
    else delete document.documentElement.dataset.calm;
  }, [calm]);

  const setPref = useCallback((next: ThemePref) => storeValue(KEY, next === "system" ? null : next), []);

  const value = useMemo(() => ({ pref, resolved, setPref }), [pref, resolved, setPref]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme braucht den ThemeProvider");
  return context;
}
