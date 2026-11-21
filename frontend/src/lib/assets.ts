import { useCallback, useEffect, useSyncExternalStore } from "react";

import { fetchAssets, type Asset } from "./api";

// Asset-Liste einmal laden und teilen (Command-Palette, Favoriten, Vergleich).
type State = { status: "idle" | "loading" | "error" } | { status: "ready"; assets: Asset[] };

let state: State = { status: "idle" };
const listeners = new Set<() => void>();

function set(next: State) {
  state = next;
  listeners.forEach((listener) => listener());
}

export function loadAssets(force = false) {
  if (state.status === "loading" || (state.status === "ready" && !force)) return;
  set({ status: "loading" });
  fetchAssets()
    .then((assets) => set({ status: "ready", assets }))
    .catch(() => set({ status: "error" }));
}

/** IDs aller bekannten Assets (lädt bei Bedarf); null, wenn die Liste nicht geladen werden konnte. */
export async function knownAssetIds(): Promise<Set<string> | null> {
  try {
    const assets = state.status === "ready" ? state.assets : await fetchAssets();
    if (state.status !== "ready") set({ status: "ready", assets });
    return new Set(assets.map((asset) => asset.id));
  } catch {
    return null;
  }
}

/** Alle Assets; lädt beim ersten Gebrauch (`enabled`). */
export function useAssets(enabled = true) {
  const current = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
    () => state,
  );
  useEffect(() => {
    if (enabled && (current.status === "idle" || current.status === "error")) loadAssets();
  }, [enabled, current.status]);
  const reload = useCallback(() => loadAssets(true), []);
  return { state: current, reload };
}
