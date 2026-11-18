import type { AssetDetail, ProfileKey } from "../../lib/api";
import { FACTORS } from "../../lib/glossary";
import { MAX_COMPARE } from "../../lib/favorites";
import { lastDays, rebase } from "../../lib/stats";

/** IDs aus `?ids=A,B,C`: nur bekannte, ohne Doppelte, höchstens MAX_COMPARE. */
export function parseCompareIds(raw: string | null, known: readonly string[]): string[] {
  if (!raw) return [];
  const set = new Set(known);
  return [...new Set(raw.split(",").map((id) => id.trim()).filter((id) => set.has(id)))].slice(0, MAX_COMPARE);
}

/** Faktoren, die mindestens ein Asset hat – in der festen Reihenfolge der Engine. */
export function factorRows(details: readonly AssetDetail[], profile: ProfileKey): string[] {
  const present = new Set<string>();
  for (const detail of details) for (const c of detail.profiles[profile]?.components ?? []) present.add(c.factor);
  const known = Object.keys(FACTORS).filter((key) => present.has(key));
  return [...known, ...[...present].filter((key) => !(key in FACTORS))];
}

/**
 * Kurse für den Vergleich: gemeinsamer Zeitraum der letzten `days` Tage, alle auf 100 normiert.
 * Beginnt das Fenster bei einem Asset später (kurze Historie), starten alle am spätesten Beginn.
 */
export function normalizedPrices(prices: readonly (readonly [string, number][])[], days: number): [string, number][][] {
  const windows = prices.map((series) => lastDays(series, days));
  const starts = windows.filter((w) => w.length > 0).map((w) => w[0]?.[0] ?? "");
  const start = starts.length ? starts.reduce((a, b) => (a > b ? a : b)) : "";
  return windows.map((window) => rebase(window.filter(([date]) => date >= start)));
}
