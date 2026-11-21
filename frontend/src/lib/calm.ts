import { storeValue, usePersistedValue } from "./usePersistentState";

// „Effekte reduzieren“: persönliche Einstellung (Konto: fx = calm), zusätzlich zu prefers-reduced-motion.
export const FX_KEY = "ef-fx";

export const isCalm = () => typeof document !== "undefined" && document.documentElement.dataset.calm === "1";

/** true, wenn die Person Effekte reduziert hat (die Systemeinstellung prüfen die Aufrufer selbst). */
export function useCalmFx(): boolean {
  return usePersistedValue(FX_KEY) === "calm";
}

export const setCalmFx = (calm: boolean) => storeValue(FX_KEY, calm ? "calm" : null);
