import { useCallback, useEffect, useState } from "react";

import { fetchAdminOverview, type AdminOverview } from "../../lib/api";
import { POLL_MS, shouldPoll } from "../../lib/adminLogic";

export type OverviewState =
  | { status: "loading" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ready"; data: AdminOverview; loadedAt: number };

/** Lädt die Admin-Übersicht; fragt nur nach, solange Aufträge laufen und die Seite sichtbar ist. */
export function useOverview(enabled: boolean) {
  const [state, setState] = useState<OverviewState>({ status: "loading" });
  const [hidden, setHidden] = useState(() => document.hidden);

  const load = useCallback(async () => {
    try {
      const data = await fetchAdminOverview();
      setState({ status: "ready", data, loadedAt: Date.now() });
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 401 || status === 403) setState({ status: "denied" });
      else setState((prev) => (prev.status === "ready" ? prev : { status: "error", message: (error as Error).message }));
    }
  }, []);

  useEffect(() => {
    if (enabled) void load();
  }, [enabled, load]);

  useEffect(() => {
    const onVisibility = () => {
      setHidden(document.hidden);
      if (!document.hidden && enabled) void load(); // zurück auf der Seite: sofort aktualisieren
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [enabled, load]);

  const jobs = state.status === "ready" ? state.data.recent_jobs : [];
  const polling = enabled && shouldPoll(jobs, hidden);
  useEffect(() => {
    if (!polling) return;
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, [polling, load]);

  return { state, reload: load, polling };
}

/** Aktuelle Zeit (ms), die alle `ms` neu gelesen wird, solange `active` (Abkühlzeit-Anzeige). */
export function useNow(active: boolean, ms = 5000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(id);
  }, [active, ms]);
  return now;
}
