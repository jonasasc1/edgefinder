import type { Asset, AssetClass, ProfileKey, ScoreEntry } from "../../lib/api";
import { levelOf, type Level } from "../../lib/score";

export const CLASS_LABEL: Record<AssetClass, string> = {
  forex: "Forex",
  index: "Indizes",
  commodity: "Rohstoffe",
  stock: "Aktien",
};

export const CLASS_ORDER: AssetClass[] = ["forex", "index", "commodity", "stock"];

export type ClassFilter = "all" | AssetClass;
export const FILTERS = ["all", ...CLASS_ORDER] as const;

export type SortKey = "score-desc" | "score-asc" | "change-1d" | "change-7d" | "name";
export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "score-desc", label: "Stärkster Score zuerst" },
  { value: "score-asc", label: "Schwächster Score zuerst" },
  { value: "change-1d", label: "Größte Änderung seit gestern" },
  { value: "change-7d", label: "Größte Änderung seit Woche" },
  { value: "name", label: "Name A–Z" },
];
export const SORT_KEYS = SORT_OPTIONS.map((option) => option.value);

export type Row = { asset: Asset; entry: ScoreEntry | undefined };

const collator = new Intl.Collator("de");

export function sortRows(rows: Row[], key: SortKey): Row[] {
  const score = (row: Row) => row.entry?.score ?? Number.NEGATIVE_INFINITY;
  const magnitude = (value: number | null | undefined) => Math.abs(value ?? 0);
  const sorted = [...rows];
  switch (key) {
    case "score-desc":
      return sorted.sort((a, b) => score(b) - score(a));
    case "score-asc":
      return sorted.sort((a, b) => (a.entry ? score(a) : Infinity) - (b.entry ? score(b) : Infinity));
    case "change-1d":
      return sorted.sort((a, b) => magnitude(b.entry?.change_1d) - magnitude(a.entry?.change_1d));
    case "change-7d":
      return sorted.sort((a, b) => magnitude(b.entry?.change_7d) - magnitude(a.entry?.change_7d));
    case "name":
      return sorted.sort((a, b) => collator.compare(a.asset.name, b.asset.name));
  }
}

export function toRows(assets: Asset[], profile: ProfileKey): Row[] {
  return assets.map((asset) => ({ asset, entry: asset.scores[profile] }));
}

/** Anzahl je Stärkestufe (−2 … +2) für die Verteilungsleiste. */
export function countLevels(rows: Row[]): Record<Level, number> {
  const counts: Record<Level, number> = { [-2]: 0, [-1]: 0, 0: 0, 1: 0, 2: 0 };
  for (const { entry } of rows) if (entry) counts[levelOf(entry.score, entry.label)] += 1;
  return counts;
}
