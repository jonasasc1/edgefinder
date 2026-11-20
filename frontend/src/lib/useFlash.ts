import { useEffect, useState } from "react";

export type Flash = { dir: "up" | "down" | null; n: number };

/**
 * Meldet, ob sich `value` gerade erhöht oder verringert hat (für ~0,9 s), damit die Zahl kurz
 * aufblitzen kann. Nicht beim ersten Anzeigen. `n` zählt hoch, damit die Animation neu startet.
 */
export function useFlash(value: number | null): Flash {
  const [prev, setPrev] = useState(value);
  const [flash, setFlash] = useState<Flash>({ dir: null, n: 0 });
  if (prev !== value) {
    setPrev(value);
    if (prev !== null && value !== null && Math.abs(value - prev) > 0.04) {
      setFlash((f) => ({ dir: value > prev ? "up" : "down", n: f.n + 1 }));
    }
  }
  useEffect(() => {
    if (!flash.dir) return;
    const timer = setTimeout(() => setFlash((f) => ({ ...f, dir: null })), 950);
    return () => clearTimeout(timer);
  }, [flash]);
  return flash;
}
