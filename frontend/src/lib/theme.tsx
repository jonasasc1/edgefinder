import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemePref = "system" | "light" | "dark";
export type Resolved = "light" | "dark";

const KEY = "ef-theme";
const query = "(prefers-color-scheme: dark)";

type ThemeContextValue = { pref: ThemePref; resolved: Resolved; setPref: (pref: ThemePref) => void };

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readPref(): ThemePref {
  try {
    const stored = localStorage.getItem(KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(readPref);
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

  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next);
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      // Speicher gesperrt: Wahl gilt nur für diese Sitzung.
    }
  }, []);

  const value = useMemo(() => ({ pref, resolved, setPref }), [pref, resolved, setPref]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme braucht den ThemeProvider");
  return context;
}
