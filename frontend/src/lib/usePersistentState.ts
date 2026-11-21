import { useCallback, useSyncExternalStore } from "react";

// Gemeinsamer Speicher für Einstellungen in localStorage. Alle Komponenten, die denselben Schlüssel
// lesen, sehen Änderungen sofort (auch wenn sie vom Konto vom Server kommen, siehe lib/account.ts).
const listeners = new Map<string, Set<() => void>>();
const userChange = new Set<(key: string) => void>();

export function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

const memory = new Map<string, string>(); // Fallback, wenn der Speicher gesperrt ist (privater Modus)

function read(key: string): string | null {
  return readStored(key) ?? memory.get(key) ?? null;
}

/** Speichert (`null` = entfernen) und benachrichtigt Leser; „user“-Änderungen lösen die Synchronisation aus. */
export function storeValue(key: string, value: string | null, source: "user" | "server" = "user") {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
    memory.delete(key);
  } catch {
    // Speicher gesperrt: Wahl gilt nur für diese Sitzung.
    if (value === null) memory.delete(key);
    else memory.set(key, value);
  }
  listeners.get(key)?.forEach((listener) => listener());
  if (source === "user") userChange.forEach((callback) => callback(key));
}

/** Registriert einen Beobachter für Änderungen durch die Person (nicht durch den Server). */
export function onUserChange(callback: (key: string) => void): () => void {
  userChange.add(callback);
  return () => userChange.delete(callback);
}

export function subscribeKey(key: string, listener: () => void): () => void {
  let set = listeners.get(key);
  if (!set) listeners.set(key, (set = new Set()));
  set.add(listener);
  return () => set.delete(listener);
}

if (typeof window !== "undefined") {
  // Änderungen aus einem anderen Tab übernehmen.
  window.addEventListener("storage", (event) => {
    if (event.key) listeners.get(event.key)?.forEach((listener) => listener());
  });
}

/** Liest einen gespeicherten Wert nur, wenn er in `valid` steht (schützt vor veralteten Werten). */
export function usePersistedValue(key: string): string | null {
  return useSyncExternalStore(
    useCallback((listener) => subscribeKey(key, listener), [key]),
    () => read(key),
    () => null,
  );
}

/** useState, das in localStorage gespeichert wird; `valid` schützt vor veralteten Werten. */
export function usePersistentState<T extends string>(
  key: string,
  fallback: T,
  valid: readonly T[],
): [T, (next: T) => void] {
  const stored = usePersistedValue(key);
  const value = stored !== null && (valid as readonly string[]).includes(stored) ? (stored as T) : fallback;
  const update = useCallback((next: T) => storeValue(key, next), [key]);
  return [value, update];
}
