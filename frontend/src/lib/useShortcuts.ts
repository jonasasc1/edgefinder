import { useEffect } from "react";
import { useNavigate } from "react-router";

// Tastenkürzel: Strg/⌘+K, „/“, „?“ und „g“ + Buchstabe (Navigation). Nicht beim Tippen in Feldern.
export const GO_TARGETS: Record<string, string> = {
  o: "/",
  m: "/makro",
  c: "/aenderungen",
  f: "/favoriten",
  b: "/bilanz",
  s: "/status",
  v: "/vergleich",
};

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function useShortcuts(actions: { togglePalette: () => void; openPalette: () => void; openHelp: () => void }) {
  const navigate = useNavigate();
  const { togglePalette, openPalette, openHelp } = actions;
  useEffect(() => {
    let pending: number | null = null;
    const clear = () => {
      if (pending !== null) window.clearTimeout(pending);
      pending = null;
    };
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        togglePalette();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented || isTypingTarget(event.target)) return;
      if (document.querySelector('[role="dialog"]')) return; // offene Fenster behalten die Tasten
      if (pending !== null) {
        const target = GO_TARGETS[event.key.toLowerCase()];
        clear();
        if (target) {
          event.preventDefault();
          navigate(target);
          return;
        }
      }
      if (event.key === "g") {
        pending = window.setTimeout(clear, 1200);
      } else if (event.key === "/") {
        event.preventDefault();
        openPalette();
      } else if (event.key === "?") {
        event.preventDefault();
        openHelp();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      clear();
    };
  }, [navigate, togglePalette, openPalette, openHelp]);
}
