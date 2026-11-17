import { motion, useTransform } from "framer-motion";

import { formatScore } from "../lib/format";
import { clampScore, levelOf, RING_COLOR, SCORE_MAX, toneOf } from "../lib/score";
import { useSpringValue } from "../lib/useSpringValue";
import { MotionText } from "./AnimatedNumber";

/*
 * Score-Ring: ein 270°-Gauge von −10 bis +10, Null oben. Der Bogen wächst von der Nullmarke
 * nach rechts (bullish) oder links (bearish); Farbe und Stärkestufe folgen dem Label.
 * Die Lücke unten gehört dem Ring – dort sitzt bei den großen Größen das Label.
 */

const SWEEP = 135; // Grad je Seite
const CENTER = 50;
const RADIUS = 41;
const MIN_ARC = 2.5; // sichtbarer Punkt, auch bei Score ≈ 0

type Size = "sm" | "md" | "lg" | "xl";

const SIZE: Record<Size, { box: string; stroke: number; number: string; label: string }> = {
  sm: { box: "size-12", stroke: 11, number: "text-footnote font-semibold", label: "" },
  md: { box: "size-24", stroke: 9, number: "text-title2 font-bold tracking-title", label: "" },
  lg: { box: "size-36", stroke: 8, number: "text-largetitle font-bold tracking-title", label: "text-footnote" },
  xl: { box: "size-52", stroke: 7, number: "text-display font-bold tracking-title", label: "text-subhead" },
};

function point(angle: number) {
  const rad = (angle * Math.PI) / 180;
  return { x: CENTER + RADIUS * Math.sin(rad), y: CENTER - RADIUS * Math.cos(rad) };
}

function arc(from: number, to: number): string {
  const a = point(from);
  const b = point(to);
  const sweep = to > from ? 1 : 0;
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${RADIUS} ${RADIUS} 0 ${large} ${sweep} ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
}

const TRACK = arc(-SWEEP, SWEEP);

type Props = {
  /** null = keine Daten */
  score: number | null;
  label?: string;
  size?: Size;
  /** Label in der Lücke unter der Zahl (nur lg/xl) */
  showLabel?: boolean;
  /** Ring wächst beim ersten Anzeigen von der Nullmarke aus */
  intro?: boolean;
  className?: string;
};

export function ScoreRing({ score, label, size = "md", showLabel = false, intro = true, className }: Props) {
  const spec = SIZE[size];
  const value = clampScore(score ?? 0);
  const level = levelOf(value, label);
  const color = score === null ? "var(--c-flat-ring)" : RING_COLOR[toneOf(level)];
  const spring = useSpringValue(value, intro ? 0 : value);
  const path = useTransform(spring, (v) => {
    const angle = (v / SCORE_MAX) * SWEEP;
    const end = Math.abs(angle) < MIN_ARC ? (angle < 0 ? -MIN_ARC : MIN_ARC) : angle;
    return arc(0, end);
  });
  const tick = point(0);
  const description =
    score === null ? "Keine Daten" : `Score ${formatScore(score)} von minus 10 bis plus 10${label ? `, ${label}` : ""}`;

  return (
    <div className={`relative inline-grid shrink-0 place-items-center ${spec.box} ${className ?? ""}`} role="img" aria-label={description}>
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full overflow-visible" aria-hidden="true">
        <path d={TRACK} fill="none" stroke="var(--c-track)" strokeWidth={spec.stroke} strokeLinecap="round" strokeDasharray={score === null ? "1 9" : undefined} />
        {score !== null && (
          <motion.path
            d={path}
            fill="none"
            strokeWidth={spec.stroke}
            strokeLinecap="round"
            style={{ stroke: color, transition: "stroke 240ms ease-out" }}
          />
        )}
        {/* Nullmarke */}
        <line x1={tick.x} y1={tick.y - spec.stroke / 2 - 2.5} x2={tick.x} y2={tick.y - spec.stroke / 2 - 0.5} stroke="var(--c-ink-3)" strokeWidth={1.4} strokeLinecap="round" />
      </svg>
      <div className="relative grid place-items-center text-center leading-none text-ink">
        {score === null ? (
          <span className={`${spec.number} text-ink-3`}>–</span>
        ) : (
          <MotionText value={spring} format={formatScore} className={spec.number} />
        )}
      </div>
      {showLabel && spec.label && (
        <span className={`absolute inset-x-0 bottom-0 text-center font-medium ${spec.label} `}>
          {score === null ? "Keine Daten" : label}
        </span>
      )}
    </div>
  );
}
