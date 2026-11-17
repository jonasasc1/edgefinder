import { motion } from "framer-motion";

import { Card } from "../../components/Card";
import { spring } from "../../lib/motion";
import type { Level } from "../../lib/score";

const SEGMENTS: { level: Level; color: string; label: string }[] = [
  { level: 2, color: "bg-bull-ring-strong", label: "Stark bullish" },
  { level: 1, color: "bg-bull-ring", label: "Bullish" },
  { level: 0, color: "bg-flat-ring", label: "Neutral" },
  { level: -1, color: "bg-bear-ring", label: "Bearish" },
  { level: -2, color: "bg-bear-ring-strong", label: "Stark bearish" },
];

/** Überblick: wie sich die gefilterten Assets auf die fünf Stufen verteilen. */
export function Distribution({ counts, total }: { counts: Record<Level, number>; total: number }) {
  const bull = counts[2] + counts[1];
  const bear = counts[-1] + counts[-2];
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-body font-bold tracking-tight">Marktbild</h2>
        <span className="num text-footnote text-ink-2">{total} Assets</span>
      </div>
      <div
        className="mt-3 flex h-3 gap-0.5 overflow-hidden rounded-chip"
        role="img"
        aria-label={`${bull} bullish, ${counts[0]} neutral, ${bear} bearish`}
      >
        {total === 0 && <div className="h-full flex-1 bg-track" />}
        {SEGMENTS.map(({ level, color }) => (
          <motion.div
            key={level}
            className={`h-full ${color}`}
            initial={false}
            animate={{ flexGrow: counts[level], opacity: counts[level] ? 1 : 0 }}
            style={{ flexBasis: 0, minWidth: 0 }}
            transition={spring}
          />
        ))}
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2 text-footnote">
        <Stat label="Bullish" value={bull} ink="text-bull-ink" />
        <Stat label="Neutral" value={counts[0]} ink="text-flat-ink" />
        <Stat label="Bearish" value={bear} ink="text-bear-ink" />
      </dl>
    </Card>
  );
}

function Stat({ label, value, ink }: { label: string; value: number; ink: string }) {
  return (
    <div>
      <dt className="text-ink-2">{label}</dt>
      <dd className={`num text-title3 font-bold tracking-title ${ink}`}>{value}</dd>
    </div>
  );
}
