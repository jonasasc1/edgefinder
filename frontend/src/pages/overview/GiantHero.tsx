import { motion } from "framer-motion";

import { MotionText } from "../../components/AnimatedNumber";
import { BrandMark, SLOGAN } from "../../components/Brand";
import { Card } from "../../components/Card";
import { EvidenceBadge } from "../../components/EvidenceBadge";
import { InfoTip } from "../../components/InfoTip";
import type { AssetClass, CalSummaryEntry } from "../../lib/api";
import { CLASS_LABEL } from "./model";
import { spring } from "../../lib/motion";
import type { Level } from "../../lib/score";
import { useSpringValue } from "../../lib/useSpringValue";

const SEGMENTS: { level: Level; color: string }[] = [
  { level: 2, color: "bg-bull-ring-strong" },
  { level: 1, color: "bg-bull-ring" },
  { level: 0, color: "bg-flat-ring" },
  { level: -1, color: "bg-bear-ring" },
  { level: -2, color: "bg-bear-ring-strong" },
];

/** Stimmung in einem Satz: aus dem Saldo von Bullish und Bearish (Anteil an allen Assets). */
export function mood(bull: number, bear: number, total: number): { title: string; text: string } {
  if (total === 0) return { title: "noch nichts", text: "Sobald Scores vorliegen, zeigt E-Giant hier die Stimmung." };
  const balance = (bull - bear) / total;
  if (balance >= 0.4) return { title: "starken Strom nach oben", text: "Die meisten Assets sind bullish." };
  if (balance >= 0.12) return { title: "Spannung nach oben", text: "Mehr Assets bullish als bearish." };
  if (balance > -0.12) return { title: "Gleichgewicht", text: "Bullish und Bearish halten sich die Waage." };
  if (balance > -0.4) return { title: "Spannung nach unten", text: "Mehr Assets bearish als bullish." };
  return { title: "starken Strom nach unten", text: "Die meisten Assets sind bearish." };
}

/**
 * Giant-Moment der Übersicht: „E-Giant sieht …“ – die Marktstimmung als Energiebalken aus Zellen
 * (bullish grün, neutral grau, bearish rot) mit großen Zahlen. Die Bildmarke steht als
 * monumentales Wasserzeichen im Hintergrund.
 */
export function GiantHero({
  counts,
  total,
  evidence,
  evidenceClasses = [],
  profileLabel = "",
}: {
  counts: Record<Level, number>;
  total: number;
  evidence?: Partial<Record<AssetClass, CalSummaryEntry>> | null;
  evidenceClasses?: AssetClass[];
  profileLabel?: string;
}) {
  const bull = counts[2] + counts[1];
  const bear = counts[-1] + counts[-2];
  const { title, text } = mood(bull, bear, total);
  return (
    <Card className="overflow-hidden p-4 sm:p-6">
      <div aria-hidden="true" className="pointer-events-none absolute -right-8 -top-10 text-ink opacity-[0.07]">
        <BrandMark size={240} />
      </div>
      <div className="relative">
        <p className="text-footnote font-semibold text-accent-ink">E-Giant sieht</p>
        <h2 className="mt-0.5 text-title1 font-extrabold tracking-title sm:text-largetitle">{title}</h2>
        <p className="mt-1 text-subhead text-ink-2">
          {text} <span className="num">{total}</span> Assets in der Auswahl.
        </p>

        <div
          className="relative mt-4 overflow-hidden rounded-control"
          role="img"
          aria-label={`${bull} bullish, ${counts[0]} neutral, ${bear} bearish`}
        >
          <div className="cells flex h-4 gap-0.5 sm:h-5">
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
          <div aria-hidden="true" className="cells-shine" />
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-2">
          <Stat label="Bullish" value={bull} ink="text-bull-ink" />
          <Stat label="Neutral" value={counts[0]} ink="text-flat-ink" />
          <Stat label="Bearish" value={bear} ink="text-bear-ink" />
        </dl>
        {evidence && evidenceClasses.length > 0 && (
          <div className="mt-4 border-t border-line pt-3">
            <p className="flex items-center gap-1 text-footnote text-ink-2">
              Aussagekraft der Scores ({profileLabel}) <InfoTip term="evidence" />
            </p>
            <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4" aria-label="Aussagekraft nach Assetklasse">
              {evidenceClasses.map((klass) => (
                <li key={klass} className="flex min-w-0 flex-col items-start gap-1">
                  <span className="text-footnote font-medium">{CLASS_LABEL[klass]}</span>
                  <EvidenceBadge evidence={evidence[klass]?.evidence ?? "zu_wenig_daten"} />
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-3 font-display text-[0.6875rem] font-medium tracking-[0.06em] text-ink-2">{SLOGAN}</p>
      </div>
    </Card>
  );
}

function Stat({ label, value, ink }: { label: string; value: number; ink: string }) {
  const spring = useSpringValue(value);
  return (
    <div>
      <dt className="text-footnote text-ink-2">{label}</dt>
      <dd className={`font-display text-display font-extrabold leading-none tracking-title ${ink}`}>
        <MotionText value={spring} format={(v) => String(Math.round(v))} />
      </dd>
    </div>
  );
}
