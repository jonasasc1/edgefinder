// Kleine Rechenhilfen für die Diagramme (rein, ohne DOM; getestet in stats.test.ts).

/** Anteil der Werte (in %), die kleiner oder gleich `value` sind – wie das COT-Perzentil im Score. */
export function percentileRank(values: readonly number[], value: number): number | null {
  if (values.length === 0) return null;
  const below = values.filter((v) => v <= value).length;
  return Math.round((below / values.length) * 100);
}

/** Reihe auf 100 am ersten Punkt normieren (Vergleich von Kursen unterschiedlicher Größe). */
export function rebase(points: readonly [string, number][]): [string, number][] {
  const first = points.find(([, value]) => value !== 0);
  if (!first) return [];
  return points.map(([date, value]) => [date, (value / first[1]) * 100]);
}

export const RANGES = [
  { value: "1m", label: "1 M", days: 31 },
  { value: "3m", label: "3 M", days: 92 },
  { value: "6m", label: "6 M", days: 183 },
  { value: "1y", label: "1 J", days: 366 },
  { value: "5y", label: "5 J", days: 1830 },
] as const;
export type RangeKey = (typeof RANGES)[number]["value"];
export const RANGE_KEYS = RANGES.map((r) => r.value);

/** Nur Punkte der letzten `days` Tage, bezogen auf den jüngsten Punkt (nicht auf „heute“). */
export function lastDays<T extends readonly [string, ...unknown[]]>(points: readonly T[], days: number): T[] {
  if (points.length === 0) return [];
  const end = new Date(`${points[points.length - 1]?.[0].slice(0, 10)}T12:00:00Z`).getTime();
  const start = end - days * 86_400_000;
  return points.filter(([date]) => new Date(`${date.slice(0, 10)}T12:00:00Z`).getTime() >= start);
}
