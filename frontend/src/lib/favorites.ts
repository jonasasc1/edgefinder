import { useSyncExternalStore } from "react";

// Favoriten: Liste von Asset-IDs. localStorage ist Cache/Offline-Fallback; mit Konto liegt der Stand am Server
// (lib/account.ts synchronisiert gebündelt). Reihenfolge = Hinzufügen.
const KEY = "ef-favorites";
export const MAX_COMPARE = 4;

/** Liest eine gespeicherte Liste; Unsinn (kaputtes JSON, Nicht-Strings, Doppelte) wird verworfen. */
export function parseIds(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return [...new Set(value.filter((v): v is string => typeof v === "string" && v.length > 0 && v.length < 32))];
  } catch {
    return [];
  }
}

/** Fügt `id` hinten an oder entfernt sie (ohne die Liste zu verändern). */
export function toggleId(ids: readonly string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

/** Favoriten zuerst (in Favoriten-Reihenfolge), Rest behält seine Reihenfolge. */
export function splitFavorites<T>(items: readonly T[], idOf: (item: T) => string, favorites: readonly string[]) {
  const byId = new Map(items.map((item) => [idOf(item), item]));
  const pinned = favorites.flatMap((id) => (byId.has(id) ? [byId.get(id) as T] : []));
  const set = new Set(favorites);
  return { pinned, rest: items.filter((item) => !set.has(idOf(item))) };
}

let current: string[] | null = null;
const listeners = new Set<() => void>();

function read(): string[] {
  if (current) return current;
  try {
    current = parseIds(localStorage.getItem(KEY));
  } catch {
    current = [];
  }
  return current;
}

function write(next: string[]) {
  current = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Speicher gesperrt (privater Modus): Favoriten gelten nur bis zum Neuladen.
  }
  listeners.forEach((listener) => listener());
}

const changeHooks = new Set<() => void>();

/** Beobachter für Änderungen durch die Person (nicht für den Abgleich mit dem Server). */
export function onFavoritesChange(callback: () => void): () => void {
  changeHooks.add(callback);
  return () => changeHooks.delete(callback);
}

export function toggleFavorite(id: string) {
  write(toggleId(read(), id));
  changeHooks.forEach((callback) => callback());
}

export const getFavorites = (): string[] => read();

/** Ersetzt den lokalen Stand (Server/Kontowechsel), ohne die Synchronisation auszulösen. */
export const replaceFavorites = (ids: string[]) => write(ids);

if (typeof window !== "undefined") {
  // Änderungen aus einem anderen Tab übernehmen.
  window.addEventListener("storage", (event) => {
    if (event.key !== KEY) return;
    current = parseIds(event.newValue);
    listeners.forEach((listener) => listener());
  });
}

/** Aktuelle Favoriten (re-rendert bei Änderung, auch aus anderen Tabs). */
export function useFavorites(): string[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    read,
    () => [],
  );
}
