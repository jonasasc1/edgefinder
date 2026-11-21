import { animate, useMotionValue, type MotionValue } from "framer-motion";
import { useEffect } from "react";

import { useReducedFx } from "./fx";

/**
 * Gibt einen MotionValue zurück, der federnd auf `target` läuft (Zahlen, Ring).
 * `initial` setzt den Startwert beim ersten Rendern (z. B. 0 → Ring wächst ein).
 * Bei reduzierter Bewegung springt der Wert sofort.
 */
export function useSpringValue(target: number, initial: number = target): MotionValue<number> {
  const value = useMotionValue(initial);
  const reduced = useReducedFx();
  useEffect(() => {
    if (reduced) {
      value.set(target);
      return;
    }
    const controls = animate(value, target, { type: "spring", stiffness: 140, damping: 22 });
    return () => controls.stop();
  }, [target, reduced, value]);
  return value;
}
