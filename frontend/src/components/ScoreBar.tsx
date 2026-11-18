import { levelOf, toneOf, type Tone } from "../lib/score";

const FILL: Record<Tone, string> = {
  "bull-strong": "bg-bull-ring-strong",
  bull: "bg-bull-ring",
  flat: "bg-flat-ring",
  bear: "bg-bear-ring",
  "bear-strong": "bg-bear-ring-strong",
};

/** Stärkestufe eines Teilscores (−1 … +1) aus dem Betrag. */
export function toneOfSubscore(value: number): Tone {
  return toneOf(levelOf(value * 10));
}

/** Mini-Gauge: Mitte = 0, Balken wächst nach rechts (bullish) oder links (bearish). `value` in [-1, 1]. */
export function ScoreBar({ value, className }: { value: number | null; className?: string }) {
  const track = `relative h-2 w-full overflow-hidden rounded-chip bg-track ${className ?? ""}`;
  if (value === null) return <div aria-hidden="true" className={`${track} opacity-50`} />;
  const clamped = Math.max(-1, Math.min(1, value));
  const width = Math.max(Math.abs(clamped) * 50, 1.5);
  return (
    <div aria-hidden="true" className={track}>
      <div
        className={`absolute inset-y-0 rounded-chip ${FILL[toneOfSubscore(clamped)]}`}
        style={{ width: `${width}%`, left: clamped >= 0 ? "50%" : `${50 - width}%` }}
      />
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-ink-3" />
    </div>
  );
}

/** Balken von 0 bis 100 (Perzentil, Long-Anteil); `marker` setzt eine Mittellinie. */
export function PercentBar({ value, className }: { value: number; className?: string }) {
  return (
    <div aria-hidden="true" className={`relative h-2 w-full overflow-hidden rounded-chip bg-track ${className ?? ""}`}>
      <div className="absolute inset-y-0 left-0 rounded-chip bg-ink-2" style={{ width: `${Math.max(1.5, Math.min(100, value))}%` }} />
    </div>
  );
}
