import type { Macro, MacroEconomy, MacroIndicator } from "../../lib/api";
import { CATEGORY_ORDER, INDICATOR_SHORT } from "../../lib/glossary";

export type Column = { key: string; label: string; category: string };

/** Spalten der Heatmap: Vereinigung aller Indikatoren, nach Kategorie sortiert (Reihenfolge der Konfiguration bleibt). */
export function heatColumns(macro: Macro): Column[] {
  const seen = new Map<string, Column>();
  for (const economy of macro.economies) {
    for (const indicator of economy.indicators) {
      if (!seen.has(indicator.key)) {
        seen.set(indicator.key, { key: indicator.key, label: INDICATOR_SHORT[indicator.key] ?? indicator.label, category: indicator.category });
      }
    }
  }
  const rank = (category: string) => {
    const index = CATEGORY_ORDER.indexOf(category);
    return index === -1 ? CATEGORY_ORDER.length : index;
  };
  return [...seen.values()].sort((a, b) => rank(a.category) - rank(b.category));
}

export function indicatorOf(economy: MacroEconomy, key: string): MacroIndicator | undefined {
  return economy.indicators.find((indicator) => indicator.key === key);
}

const MAX_SHARE = 45; // Prozent Farbanteil; darüber leidet der Textkontrast im Dunkelmodus
const MIN_SHARE = 7;
const FULL_AT = 0.5; // Score, ab dem die Farbe ihre volle Stärke hat (typische Werte liegen bei ±0,2)

/** Farbfläche einer Zelle: Richtung aus dem Vorzeichen, Stärke aus dem Betrag; null = keine Wertung. */
export function heatShare(score: number | null): { tone: "bull" | "bear" | "flat"; share: number } {
  if (score === null || Math.abs(score) < 0.02) return { tone: "flat", share: 0 };
  const strength = Math.min(1, Math.abs(score) / FULL_AT);
  return { tone: score > 0 ? "bull" : "bear", share: Math.round(MIN_SHARE + strength * (MAX_SHARE - MIN_SHARE)) };
}
