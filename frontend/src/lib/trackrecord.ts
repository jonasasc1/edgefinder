// Bilanz (Forward-Test): Klartexte aus den Zahlen der API. Sachlich, ohne Handlungsempfehlung:
// „geeicht“ heißt „Aussage belastbar geprüft“, nie „profitabel“.

import type { DriftStatus, FactorDrift, Trackrecord } from "./api";
import { formatDate, formatDecimal, formatPctSigned } from "./format";

export const DRIFT_LABEL: Record<DriftStatus, string> = {
  zu_frueh: "zu früh",
  im_rahmen: "im Rahmen der Eichung",
  schwaecher: "schwächer als geeicht",
  besser: "besser als geeicht",
  gegenlaeufig: "gegenläufig",
  ohne_eichung: "ohne Eichung",
};

export const DRIFT_SHORT: Record<DriftStatus, string> = {
  zu_frueh: "zu früh",
  im_rahmen: "im Rahmen",
  schwaecher: "schwächer",
  besser: "besser",
  gegenlaeufig: "gegenläufig",
  ohne_eichung: "ohne Eichung",
};

export const FACTOR_STATUS_LABEL: Record<FactorDrift["status"], string> = {
  zu_frueh: "zu früh",
  im_rahmen: "im Rahmen",
  schwaecher: "schwächer als im Backtest",
  gegenlaeufig: "gegenläufig",
  kein_vergleich: "kein Vergleich möglich",
};

/** Kopfzeile: ehrlich über Datenmenge und frühesten Zeitpunkt belastbarer Aussagen. */
export function headerText(t: Trackrecord): string {
  if (!t.live_since) return "Der Live-Betrieb hat noch keine Signale erzeugt.";
  const since = formatDate(t.live_since);
  const count = t.evaluated === 1 ? "1 ausgewertetes Signal" : `${t.evaluated} ausgewertete Signale`;
  const reliable = t.reliable_from ? ` Belastbare Aussagen sind frühestens ab ${formatDate(t.reliable_from)} möglich.` : "";
  return `Live seit ${since}, bisher ${count}, ${t.open} laufen noch.${reliable}`;
}

export const progressPct = (progress: number) => Math.round(Math.max(0, Math.min(1, progress)) * 100);

/** „+0,8 Prozentpunkte“ aus einem Bruchteil (0,008). */
export function formatEdge(edge: number | null): string {
  if (edge === null) return "–";
  return formatPctSigned(edge * 100, 2).replace(" %", " PP");
}

export const formatShare = (share: number | null) => (share === null ? "–" : `${formatDecimal(share * 100, 0)} %`);

/** Die Gruppe hat noch keine auswertbaren Signale (leerer Zustand statt Nullen). */
export const isEmptyGroup = (n: number) => n === 0;

/** Schwächste Stelle auf dem Weg zu „geeicht“, damit klar ist, was noch fehlt. */
export function missingText(t: Trackrecord, group: { n_eff: number; months: number; weeks: number }): string {
  const c = t.criteria;
  const parts: string[] = [];
  if (group.n_eff < c.min_n_eff) parts.push(`${formatDecimal(group.n_eff, 0)} von ${formatDecimal(c.min_n_eff, 0)} unabhängigen Fällen`);
  if (group.months < c.min_months) parts.push(`${formatDecimal(group.months, 1)} von ${formatDecimal(c.min_months, 0)} Monaten`);
  if (group.weeks < c.min_weeks) parts.push(`${group.weeks} von ${c.min_weeks} Wochen`);
  return parts.join(" · ");
}

/** Warnungen der Faktor-Drift als Sätze (nur Meldung, keine automatische Änderung). */
export function factorWarning(f: FactorDrift, factor: string, klass: string): string {
  return `${factor} (${klass}): seit ${f.weeks_against} ${f.weeks_against === 1 ? "Woche" : "Wochen"} gegenläufig zum Backtest`;
}
