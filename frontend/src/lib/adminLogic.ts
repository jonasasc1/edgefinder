// Admin-Bereich: reine Logik (Sichtbarkeit, Job-Zustände, Polling, Prompt für Claude). Die Berechtigung
// entscheidet allein der Server (403); das Frontend blendet den Bereich nur ein oder aus.

export type JobKey = "review" | "maintain" | "score" | "evaluate";
export type JobStatus = "queued" | "running" | "ok" | "error" | "rejected";

export type AdminJob = {
  id: number;
  job: string;
  requested_by: string | null;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  status: JobStatus;
  summary: string | null;
  log_tail?: string | null;
};

export const POLL_MS = 3000;

/** Admin-Eintrag nur zeigen, wenn das Konto geladen ist und der Server `is_admin` gemeldet hat. */
export function adminVisible(status: string, isAdmin: boolean | undefined): boolean {
  return status === "ready" && isAdmin === true;
}

export const isActive = (job: Pick<AdminJob, "status">) => job.status === "queued" || job.status === "running";

/** Polling nur, solange ein Auftrag wartet oder läuft und die Seite sichtbar ist. */
export function shouldPoll(jobs: readonly Pick<AdminJob, "status">[], hidden: boolean): boolean {
  return !hidden && jobs.some(isActive);
}

export type Phase = "idle" | "queued" | "running" | "done" | "failed";

/** Zustand eines Job-Typs für die Karte: neuester Auftrag dieses Typs entscheidet. */
export function phaseOf(jobs: readonly AdminJob[], job: string): { phase: Phase; latest: AdminJob | null } {
  const latest = jobs.filter((j) => j.job === job).sort((a, b) => b.id - a.id)[0] ?? null;
  if (!latest) return { phase: "idle", latest: null };
  if (latest.status === "queued") return { phase: "queued", latest };
  if (latest.status === "running") return { phase: "running", latest };
  return { phase: latest.status === "ok" ? "done" : "failed", latest };
}

export const PHASE_LABEL: Record<Phase, string> = {
  idle: "Bereit",
  queued: "Wartet",
  running: "Läuft",
  done: "Fertig",
  failed: "Fehler",
};

/** „in 8 Min.“ / „in 45 Sek.“ bzw. null, wenn der Auftrag sofort möglich ist. */
export function cooldownText(waitSeconds: number): string | null {
  if (waitSeconds <= 0) return null;
  if (waitSeconds < 90) return `in ${Math.ceil(waitSeconds)} Sek.`;
  return `in ${Math.ceil(waitSeconds / 60)} Min.`;
}

export const REGELN = [
  "Hypothese ökonomisch begründen, nicht nur „sieht besser aus“.",
  "Test auf Training/OOS und auf dem Forward-Zeitraum seit der letzten Änderung (echter Holdout, nie zum Tuning benutzen).",
  "Höchstens 2 bis 3 Varianten; Mindestabstand 4 Wochen und die Live-n_eff-Mindestmenge zur letzten Änderung beachten.",
  "Vorschlag mit Zahlen an Jonas; Übernahme nur nach seiner Freigabe (dann scoring.model_version erhöhen).",
];

/** Fertiger Auftragstext für Claude: Regeln des Modellpflege-Zyklus + Bericht + klare Grenze. */
export function buildClaudePrompt(reportMd: string | null, stand: string | null): string {
  const lines = [
    "Du arbeitest im Projekt edgefinder (E-Giant). Lies zuerst CLAUDE.md, Abschnitt „Modellpflege-Zyklus“.",
    "",
    `Aufgabe: Prüfe die folgende Bilanz${stand ? ` (Stand ${stand})` : ""} und sage, ob etwas auffällig ist (Drift, gegenläufige Faktoren, zu wenig Daten).`,
    "",
    "Regeln des Modellpflege-Zyklus:",
    ...REGELN.map((rule, index) => `${index + 1}. ${rule}`),
    "",
    "WICHTIG: Nur analysieren und Vorschläge machen. Keine Änderungen an Code, Konfiguration oder Server und kein Deploy ohne ausdrückliche Freigabe von Jonas.",
    "Keine Kauf- oder Verkaufsempfehlungen; „geeicht“ heißt „Aussage geprüft“, nie „profitabel“.",
    "",
    "Bericht:",
    "",
    reportMd?.trim() ? reportMd.trim() : "(Es liegt noch kein Prüfbericht vor. Bitte zuerst „Prüfung jetzt ausführen“ starten.)",
    "",
  ];
  return lines.join("\n");
}

export type DriftGroup = {
  profile: string;
  asset_class: string;
  n: number;
  n_eff: number;
  weeks: number;
  hit: number | null;
  base_hit: number | null;
  edge: number | null;
  cal_edge: number | null;
  status: string;
};

/** Gruppen aus dem Drift-Bericht; unbekannte Formen ergeben eine leere Liste (kein Absturz). */
export function groupsOf(drift: unknown): DriftGroup[] {
  const groups = (drift as { groups?: unknown } | null)?.groups;
  if (!Array.isArray(groups)) return [];
  return groups.filter((g): g is DriftGroup => typeof g === "object" && g !== null && typeof (g as DriftGroup).profile === "string");
}

export function driftNumber(drift: unknown, key: string): number | null {
  const value = (drift as Record<string, unknown> | null)?.[key];
  return typeof value === "number" ? value : null;
}

export function driftText(drift: unknown, key: string): string | null {
  const value = (drift as Record<string, unknown> | null)?.[key];
  return typeof value === "string" ? value : null;
}

/** Aussagekräftige Meldung zu einer Server-Antwort (detail), sonst Standardtext je Status. */
export function errorMessage(status: number, detail: string | null): string {
  if (detail) return detail;
  if (status === 403) return "Kein Zugriff.";
  if (status === 401) return "Nicht angemeldet.";
  return `Fehler (HTTP ${status}).`;
}
