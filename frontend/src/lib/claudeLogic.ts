// Claude-Analyse (Etappe q): reine Logik für Zustände, Polling, Protokoll-Filter, Download.
// Die Berechtigung entscheidet allein der Server; hier wird nur dargestellt.

export type ClaudeState = "preparing" | "queued" | "running" | "ok" | "error" | "timeout" | "stale";

export type ClaudeRun = {
  id: number;
  state: ClaudeState;
  requested_at: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  exit_code?: number | null;
  turns?: number | null;
  cost_usd?: number | null;
  message?: string | null;
};

export type ClaudeOverview = {
  enabled: boolean;
  installed: boolean;
  active_id: number | null;
  max_turns: number;
  runtime_max_seconds: number;
  retention_days: number;
  runs_today: number;
  max_runs_per_day: number;
  cooldown_minutes: number;
  wait_seconds: number;
};

export type ClaudeRunDetail = ClaudeRun & {
  analysis_md: string | null;
  proposals: { name: string; text: string }[];
  has_audit: boolean;
};

export type AuditEntry = {
  t?: string;
  event?: string;
  tool?: string | null;
  input?: string;
  result?: string;
  decision?: string;
  reason?: string;
  note?: string;
  raw?: string;
};

export const CLAUDE_POLL_MS = 3000;
export const CLAUDE_GUIDE = "deploy/claude-review/README.md";

export const isClaudeActive = (run: Pick<ClaudeRun, "state">) => run.state === "preparing" || run.state === "queued" || run.state === "running";

/** Polling nur, solange ein Lauf aktiv ist und die Seite sichtbar ist. */
export function shouldPollClaude(runs: readonly Pick<ClaudeRun, "state">[], hidden: boolean): boolean {
  return !hidden && runs.some(isClaudeActive);
}

export const STATE_LABEL: Record<ClaudeState, string> = {
  preparing: "Wird vorbereitet",
  queued: "Wartet auf Start",
  running: "Läuft",
  ok: "Fertig",
  error: "Fehler",
  timeout: "Zeitlimit",
  stale: "Nicht gestartet",
};

export type ClaudeTone = "flat" | "bull" | "bear";
export const STATE_TONE: Record<ClaudeState, ClaudeTone> = {
  preparing: "flat",
  queued: "flat",
  running: "flat",
  ok: "bull",
  error: "bear",
  timeout: "bear",
  stale: "bear",
};

/** Fortschritt in Stufen (Vorbereiten → Warten → Läuft → Fertig); Fehlerzustände zeigen die letzte Stufe. */
export function stepOf(state: ClaudeState): number {
  return { preparing: 1, queued: 2, running: 3, ok: 4, error: 4, timeout: 4, stale: 2 }[state];
}

/** „3 Min. 20 Sek.“ bzw. „45 Sek.“; null ohne Angabe. */
export function durationText(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return null;
  const s = Math.round(seconds);
  if (s < 60) return `${s} Sek.`;
  return `${Math.floor(s / 60)} Min. ${String(s % 60).padStart(2, "0")} Sek.`;
}

export type StartInfo = { canStart: boolean; reason: string | null };

/** Ob der Button aktiv ist; `reason` erklärt, warum nicht (Reihenfolge wie auf dem Server). */
export function startInfo(o: ClaudeOverview, waitSeconds: number, busy: boolean): StartInfo {
  if (!o.enabled) return { canStart: false, reason: "Der Prüfagent ist nicht aktiviert." };
  if (!o.installed) return { canStart: false, reason: "Der Prüfagent ist auf dem Server nicht installiert." };
  if (busy || o.active_id !== null) return { canStart: false, reason: "Es läuft bereits eine Analyse." };
  if (o.runs_today >= o.max_runs_per_day) return { canStart: false, reason: `Tageslimit erreicht (${o.max_runs_per_day} in 24 Stunden).` };
  if (waitSeconds > 0) return { canStart: false, reason: `Abkühlzeit: wieder möglich in ${Math.ceil(waitSeconds / 60)} Min.` };
  return { canStart: true, reason: null };
}

export type Availability = "ready" | "disabled" | "not-installed";
export const availability = (o: ClaudeOverview): Availability => (!o.enabled ? "disabled" : !o.installed ? "not-installed" : "ready");

export type AuditFilter = "all" | "tools" | "denied" | "errors";

/** Protokoll-Einträge filtern: nur Werkzeuge, nur Ablehnungen oder nur Fehlerergebnisse. */
export function filterAudit(entries: readonly AuditEntry[], filter: AuditFilter): AuditEntry[] {
  switch (filter) {
    case "tools":
      return entries.filter((e) => e.event === "PreToolUse" || e.event === "PostToolUse");
    case "denied":
      return entries.filter((e) => e.decision === "deny");
    case "errors":
      return entries.filter((e) => e.event === "PostToolUse" && /error|fehler|denied|traceback/i.test(e.result ?? ""));
    default:
      return [...entries];
  }
}

export function auditSummary(entry: AuditEntry): string {
  if (entry.raw) return entry.raw;
  if (entry.event === "Stop") return entry.note ?? "Sitzung beendet";
  const tool = entry.tool ?? "?";
  if (entry.event === "PreToolUse") return `${tool}: ${entry.input ?? ""}${entry.decision === "deny" ? ` – abgelehnt (${entry.reason ?? ""})` : ""}`;
  return `${tool} → ${entry.result ?? ""}`;
}

export const analysisFilename = (id: number) => `claude-analyse-${id}.md`;

/** Download im Browser (Blob, kein Server-Pfad). */
export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
