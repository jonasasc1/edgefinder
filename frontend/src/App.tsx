import { useEffect, useState } from "react";

type Health = { status: string; version: string; schema_version: number };

// Platzhalter für das Projektgerüst (Etappe a). Design-System und Seiten folgen
// in den Etappen e und f.
export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((body: Health) => setHealth(body))
      .catch(() => setFailed(true));
  }, []);

  return (
    <main className="mx-auto max-w-xl p-6 font-sans">
      <h1 className="text-2xl font-bold">edgefinder</h1>
      <p className="mt-2 tabular-nums">
        {failed && "API nicht erreichbar."}
        {health && `API ${health.status} · Version ${health.version} · Schema ${health.schema_version}`}
        {!failed && !health && "Verbinde …"}
      </p>
    </main>
  );
}
