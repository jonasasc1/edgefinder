// Anzeige der Scorecard-Zeilen: Einheiten, Vorzeichen, Signal-Pillen (rein, getestet).
import type { ScorecardRow, Signal } from "../../lib/api";
import { formatCompact, formatDecimal, formatInt } from "../../lib/format";
import type { Tone } from "../../lib/score";

const MINUS = "−";
const sign = (value: number, text: string) => (Number(text.replace(/\./g, "").replace(",", ".")) === 0 ? text : (value > 0 ? "+" : MINUS) + text);
const abs = (value: number, digits: number) => formatDecimal(Math.abs(value), digits);

/** Wert (Actual/Vorwert) mit Einheit. */
export function formatCell(unit: string, value: number | null): string {
  if (value === null) return "–";
  switch (unit) {
    case "%":
      return `${formatDecimal(value, 2)} %`;
    case "count":
      return formatInt(value);
    case "k":
      return `${formatInt(value)} Tsd.`;
    case "index":
      return formatDecimal(value, 1);
    case "x":
      return `${formatDecimal(value, 1)}×`;
    case "shares":
      return formatCompact(value);
    case "usd":
      return Math.abs(value) >= 10_000 ? `${formatCompact(value)} $` : `${formatDecimal(value, 2)} $`;
    default:
      return formatDecimal(value, 2);
  }
}

/** Änderung mit Vorzeichen; Prozentpunkte als „PP“, relative Änderung als „%“. */
export function formatChange(row: Pick<ScorecardRow, "unit" | "change_unit">, change: number | null): string {
  if (change === null) return "–";
  const unit = row.change_unit ?? row.unit;
  switch (unit) {
    case "pp":
      return `${sign(change, abs(change, 2))} PP`;
    case "%":
      return `${sign(change, abs(change, 1))} %`;
    case "k":
      return `${sign(change, formatInt(Math.abs(change)))} Tsd.`;
    case "count":
      return sign(change, formatInt(Math.abs(change)));
    default:
      return sign(change, abs(change, 2));
  }
}

export const formatSurprise = (value: number | null) => (value === null ? "–" : `${sign(value, abs(value, 1))} %`);

export const SIGNAL_LABEL: Record<Signal, string> = { bullish: "Bullish", bearish: "Bearish", neutral: "Neutral" };

/** Pillenfarbe: gefüllt (stark) ab |Score| ≥ 0,6, wie die Stufen des Gesamtscores. */
export function signalTone(signal: Signal | null, score: number | null): Tone {
  if (signal === "bullish") return score !== null && score >= 0.6 ? "bull-strong" : "bull";
  if (signal === "bearish") return score !== null && score <= -0.6 ? "bear-strong" : "bear";
  return "flat";
}

const dateCompact = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" });
export const formatDateCompact = (iso: string | null) => (iso ? dateCompact.format(new Date(`${iso.slice(0, 10)}T12:00:00`)) : "–");
