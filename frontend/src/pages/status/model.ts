import type { SourceStatus } from "../../lib/api";
import type { Tone } from "../../lib/score";

export type Health = "ok" | "partial" | "stale" | "failed" | "never" | "off";

/** Zustand einer Quelle für die Anzeige (verständlich statt Rohstatus). */
export function healthOf(source: SourceStatus): Health {
  if (!source.enabled) return "off";
  if (!source.last_success) return "never";
  if (source.stale) return "stale";
  if (source.last_run_status === "error") return "failed";
  if (source.last_run_status === "partial") return "partial";
  return "ok";
}

export const HEALTH: Record<Health, { label: string; tone: Tone; problem: boolean }> = {
  ok: { label: "Aktuell", tone: "bull", problem: false },
  partial: { label: "Teilweise Lücken", tone: "flat", problem: false },
  stale: { label: "Veraltet", tone: "bear", problem: true },
  failed: { label: "Letzter Lauf fehlgeschlagen", tone: "bear", problem: true },
  never: { label: "Noch nie geladen", tone: "bear", problem: true },
  off: { label: "Deaktiviert", tone: "flat", problem: false },
};

/** Probleme zuerst, sonst Reihenfolge der Konfiguration. */
export function sortSources(sources: readonly SourceStatus[]): SourceStatus[] {
  return sources
    .map((source, index) => ({ source, index, problem: HEALTH[healthOf(source)].problem }))
    .sort((a, b) => Number(b.problem) - Number(a.problem) || a.index - b.index)
    .map((entry) => entry.source);
}

/** Wartungsjobs (keine Datenquellen): ihr Ausfall betrifft Bilanz und Eichung, nicht die Scores. */
export const JOB_SOURCES: readonly string[] = ["maintain", "evaluate"];
