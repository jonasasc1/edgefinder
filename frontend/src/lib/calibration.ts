// Eichung: Klartext aus den Kalibrierungsdaten (Zahlen kommen von der API, Sätze entstehen hier).
// Sachlich, keine Handlungsempfehlung: beschrieben wird, was ein Score-Bereich historisch gebracht hat.

import type { AssetCalibration, CalCell, CalPeriods, Evidence } from "./api";
import { formatDecimal, formatPctSigned } from "./format";

export const EVIDENCE_LABEL: Record<Evidence, string> = {
  belegt: "belegt",
  schwach: "schwach belegt",
  kein_vorteil: "kein belegter Vorteil",
  zu_wenig_daten: "zu wenig Daten",
  neutral: "keine Richtungsaussage",
};

/** Kurzform für enge Stellen (Chips, Übersicht). */
export const EVIDENCE_SHORT: Record<Evidence, string> = {
  belegt: "belegt",
  schwach: "schwach",
  kein_vorteil: "kein Vorteil",
  zu_wenig_daten: "zu wenig Daten",
  neutral: "neutral",
};

const MINUS = "−";
const signed = (v: number) => (v > 0 ? "+" : v < 0 ? MINUS : "") + String(Math.abs(v));

/** Score-Bereich als Text: „+2 bis +6“, „ab +6“, „bis −6“ (Grenzen aus scoring.labels, ±10 = offen). */
export function bucketRange(low: number, high: number): string {
  if (high >= 10) return `ab ${signed(low)}`;
  if (low <= -10) return `bis ${signed(high)}`;
  return `${signed(low)} bis ${signed(high)}`;
}

const pct0 = (share: number) => `${formatDecimal(share * 100, 0)} %`;

/** Zeitraum der Eichung: „2013–2026“. */
export function periodText(cal: { first_date: string | null; data_through: string | null }): string {
  if (!cal.first_date || !cal.data_through) return "";
  const a = cal.first_date.slice(0, 4);
  const b = cal.data_through.slice(0, 4);
  return a === b ? a : `${a}–${b}`;
}

/** Anteil „Kurs in Signalrichtung“ und dessen Basis: bullish → stieg, bearish → fiel, neutral → stieg. */
export function rateOf(cell: CalCell, direction: -1 | 0 | 1): { verb: string; value: number; base: number } | null {
  if (direction < 0) {
    if (cell.hit == null || cell.base_hit == null) return null;
    return { verb: "fiel", value: cell.hit, base: cell.base_hit };
  }
  if (cell.up == null || cell.base_up == null) return null;
  return { verb: "stieg", value: cell.up, base: cell.base_up };
}

/**
 * Der Satz der Karte „Einordnung“, z. B.
 * „Bei Scores in diesem Bereich (+2 bis +6, Aktien, Swing, 10 Tage, 2013–2026): Kurs stieg in 54 % der Fälle
 * (Basis 58 %), Ø +0,4 % – schwach belegt.“
 */
export function headline(cal: AssetCalibration, classLabel: string, profileLabel: string): string | null {
  if (!cal.available || !cal.bucket || !cal.stats || !cal.horizon || !cal.evidence) return null;
  const all = cal.stats.all;
  const scope = `${bucketRange(cal.bucket.low, cal.bucket.high)}, ${classLabel}, ${profileLabel}, ${cal.horizon} Tage, ${periodText(cal)}`;
  const rate = rateOf(all, cal.bucket.direction);
  if (!rate || all.mean == null) return `Bei Scores in diesem Bereich (${scope}) liegen zu wenige Fälle vor – ${EVIDENCE_LABEL.zu_wenig_daten}.`;
  return `Bei Scores in diesem Bereich (${scope}): Kurs ${rate.verb} in ${pct0(rate.value)} der Fälle (Basis ${pct0(rate.base)}), Ø ${formatPctSigned(all.mean * 100, 1)} – ${EVIDENCE_LABEL[cal.evidence]}.`;
}

/** Klartext zur Klasse, wenn der Score dort historisch keinen Vorteil gezeigt hat. */
export function noEdgeText(cal: AssetCalibration, classLabel: string, profileLabel: string): string | null {
  if (cal.class_evidence !== "kein_vorteil") return null;
  return `Für diese Klasse (${classLabel}, ${profileLabel}) hat der Score historisch keinen Vorteil gegenüber Zufall gezeigt.`;
}

export type Stability = "gleichsinnig" | "wechselt" | "unklar";

/** Training und Out-of-Sample im Vergleich: gleiches Vorzeichen des Vorteils oder nicht. */
export function stability(stats: CalPeriods | null, direction: -1 | 0 | 1): Stability {
  if (!stats || direction === 0) return "unklar";
  const a = stats.train.edge;
  const b = stats.oos.edge;
  if (a == null || b == null) return "unklar";
  return Math.sign(a) === Math.sign(b) && a !== 0 ? "gleichsinnig" : "wechselt";
}

export const STABILITY_TEXT: Record<Stability, string> = {
  gleichsinnig: "Training und Out-of-Sample zeigen dasselbe Vorzeichen.",
  wechselt: "Das Vorzeichen wechselt zwischen Training und Out-of-Sample: der Zusammenhang ist instabil.",
  unklar: "Für einen Vergleich fehlen Daten.",
};

/** „5 von 7 Faktoren bullish“ (Richtung des Gesamtscores; bei Neutral die Verteilung). */
export function agreementText(a: { direction: -1 | 0 | 1; total: number; same: number; bullish: number; bearish: number; neutral: number }): string {
  if (a.direction > 0) return `${a.same} von ${a.total} Faktoren bullish`;
  if (a.direction < 0) return `${a.same} von ${a.total} Faktoren bearish`;
  return `${a.bullish} bullish, ${a.bearish} bearish, ${a.neutral} neutral (von ${a.total})`;
}

/** Aussagekraft der Faktor-Übereinstimmung laut Eichung (nur Hinweis, nie als Beleg überhöht). */
export function agreementEvidenceText(group: "high" | "low" | null, evidence: Evidence | null): string {
  if (!group || !evidence) return "Für die Übereinstimmung liegt keine Eichung vor.";
  const which = group === "high" ? "Hohe" : "Niedrige";
  if (evidence === "belegt") return `${which} Übereinstimmung: historisch ein belegter Vorteil in dieser Klasse.`;
  if (evidence === "schwach") return `${which} Übereinstimmung: nur ein schwacher Hinweis, nicht belegt.`;
  if (evidence === "kein_vorteil") return `${which} Übereinstimmung: historisch kein Vorteil, die Zahl ist hier nicht belegt.`;
  return `${which} Übereinstimmung: zu wenig Daten.`;
}
