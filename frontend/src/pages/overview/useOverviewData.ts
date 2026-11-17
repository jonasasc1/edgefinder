import { useCallback, useEffect, useState } from "react";

import { fetchAssets, fetchProfiles, type Asset, type Profile } from "../../lib/api";

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; assets: Asset[]; profiles: Profile[] };

/** Lädt Assets und Profile; `reload` startet den Abruf neu (Fehlerzustand → „Erneut laden“). */
export function useOverviewData() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetchAssets(controller.signal), fetchProfiles(controller.signal)])
      .then(([assets, profiles]) => setState({ status: "ready", assets, profiles }))
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") setState({ status: "error" });
      });
    return () => controller.abort();
  }, [attempt]);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  return { state, reload };
}
