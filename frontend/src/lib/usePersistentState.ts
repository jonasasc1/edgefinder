import { useCallback, useState } from "react";

/** useState, das in localStorage gespeichert wird; `valid` schützt vor veralteten Werten. */
export function usePersistentState<T extends string>(
  key: string,
  fallback: T,
  valid: readonly T[],
): [T, (next: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key) as T | null;
      return stored && valid.includes(stored) ? stored : fallback;
    } catch {
      return fallback;
    }
  });
  const update = useCallback(
    (next: T) => {
      setValue(next);
      try {
        localStorage.setItem(key, next);
      } catch {
        // Speicher gesperrt (privater Modus): Wahl gilt nur für diese Sitzung.
      }
    },
    [key],
  );
  return [value, update];
}
