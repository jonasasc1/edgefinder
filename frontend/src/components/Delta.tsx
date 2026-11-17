import { formatDelta } from "../lib/format";

/** Änderung eines Scores: Dreieck + Wert, grün/rot nur bei spürbarer Bewegung (≥ 0,05). */
export function Delta({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="num text-ink-2">–</span>;
  const up = value >= 0.05;
  const down = value <= -0.05;
  const color = up ? "text-bull-ink" : down ? "text-bear-ink" : "text-ink-2";
  return (
    <span className={`num inline-flex items-center gap-1 font-medium ${color}`}>
      <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true" className={up ? "" : down ? "rotate-180" : "opacity-0"}>
        <path d="M4 1.2 7.2 6.6H.8L4 1.2Z" fill="currentColor" />
      </svg>
      {formatDelta(value)}
    </span>
  );
}
