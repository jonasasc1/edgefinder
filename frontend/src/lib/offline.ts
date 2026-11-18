import { useSyncExternalStore } from "react";

// Stand der zuletzt angezeigten Daten, wenn sie nur aus dem Zwischenspeicher des Service Workers
// stammen (offline). null = Daten sind frisch vom Server.
let cachedAt: string | null = null;
const listeners = new Set<() => void>();

export function setOffline(value: string | null) {
  if (value === cachedAt) return;
  cachedAt = value;
  listeners.forEach((listener) => listener());
}

export function useOfflineSince(): string | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => cachedAt,
    () => null,
  );
}
