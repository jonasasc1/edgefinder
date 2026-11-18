import { useCallback, useEffect, useState } from "react";

export type ApiState<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T };

/**
 * Lädt Daten beim Einblenden und wenn sich `deps` ändern (nur Texte/Zahlen); `reload` startet neu
 * (Fehlerzustand → „Erneut laden“). Solange die Antwort zu anderen `deps` gehört, gilt „loading“.
 */
export function useApi<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly (string | number)[]) {
  const [attempt, setAttempt] = useState(0);
  const key = `${deps.join("|")}#${attempt}`;
  const [result, setResult] = useState<{ key: string; state: ApiState<T> } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal)
      .then((data) => setResult({ key, state: { status: "ready", data } }))
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") setResult({ key, state: { status: "error", message: (error as Error).message } });
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `load` ist über `key` gesteuert
  }, [key]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  const state: ApiState<T> = result?.key === key ? result.state : { status: "loading" };
  return { state, reload };
}
