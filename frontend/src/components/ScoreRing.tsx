import { motion, useReducedMotion, useTransform } from "framer-motion";
import { useState } from "react";

import { formatScore } from "../lib/format";
import { jitter } from "../lib/fx";
import { clampScore, CORE_COLOR, levelOf, RING_COLOR, SCORE_MAX, toneOf } from "../lib/score";
import { useFlash } from "../lib/useFlash";
import { useSpringValue } from "../lib/useSpringValue";
import { MotionText } from "./AnimatedNumber";

/*
 * Spannungs-Gauge: ein 270°-Energiebogen von −10 bis +10, Null oben. Der Bogen wächst von der
 * Nullmarke nach rechts (bullish) oder links (bearish); Farbe und Stärkestufe folgen dem Label.
 * Der Bogen hat einen hellen Kern und glüht. Ändert sich der Wert (oder lädt ein großer Ring),
 * entlädt sich ein Blitz entlang des Bogens; ab |Score| ≥ 6 knistern Funken an der Spitze.
 * Die Lücke unten gehört dem Ring – dort sitzt bei den großen Größen das Label.
 */

const SWEEP = 135; // Grad je Seite
const CENTER = 50;
const RADIUS = 41;
const MIN_ARC = 2.5; // sichtbarer Punkt, auch bei Score ≈ 0
const SPARK_SCORE = 6;

type Size = "sm" | "md" | "lg" | "xl";

const SIZE: Record<Size, { box: string; stroke: number; number: string; label: string; glow: boolean; bolt: boolean }> = {
  sm: { box: "size-12", stroke: 11, number: "text-footnote font-semibold", label: "", glow: false, bolt: false },
  md: { box: "size-24", stroke: 9, number: "font-display text-title2 font-bold tracking-title", label: "", glow: true, bolt: false },
  lg: { box: "size-36", stroke: 8, number: "font-display text-largetitle font-bold tracking-title", label: "text-footnote", glow: true, bolt: true },
  xl: { box: "size-52", stroke: 7, number: "font-display text-giant font-extrabold tracking-title", label: "text-subhead", glow: true, bolt: true },
};

function point(angle: number, radius = RADIUS) {
  const rad = (angle * Math.PI) / 180;
  return { x: CENTER + radius * Math.sin(rad), y: CENTER - radius * Math.cos(rad) };
}

function arc(from: number, to: number): string {
  const a = point(from);
  const b = point(to);
  const sweep = to > from ? 1 : 0;
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${RADIUS} ${RADIUS} 0 ${large} ${sweep} ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
}

/** Blitzform entlang des Bogens von der Nullmarke bis `end` (Grad): Zickzack um die Bogenlinie. */
function boltPath(end: number, amp: number): string {
  const steps = Math.max(3, Math.ceil(Math.abs(end) / 11));
  return Array.from({ length: steps + 1 }, (_, i) => {
    const edge = i === 0 || i === steps;
    const radius = RADIUS + (edge ? 0 : jitter(i * 2.9 + Math.sign(end)) * amp);
    const angle = (end * i) / steps + (edge ? 0 : jitter(i * 4.3) * 2.5);
    const p = point(angle, radius);
    return `${i ? "L" : "M"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
  }).join(" ");
}

const TRACK = arc(-SWEEP, SWEEP);

const angleOf = (value: number) => {
  const angle = (value / SCORE_MAX) * SWEEP;
  return Math.abs(angle) < MIN_ARC ? (angle < 0 ? -MIN_ARC : MIN_ARC) : angle;
};

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
  const reduced = useReducedMotion();
  const value = clampScore(score ?? 0);
  const level = levelOf(value, label);
  const tone = toneOf(level);
  const color = score === null ? "var(--c-flat-ring)" : RING_COLOR[tone];
  const spring = useSpringValue(value, intro ? 0 : value);
  const path = useTransform(spring, (v) => arc(0, angleOf(v)));
  const tick = point(0);
  const flash = useFlash(score);

  // Blitz: einmal beim Laden (nur große Ringe) und bei jeder Wertänderung
  const [seen, setSeen] = useState(score);
  const [zap, setZap] = useState(spec.bolt && intro && score !== null ? 1 : 0);
  if (seen !== score) {
    setSeen(score);
    if (score !== null && seen !== null) setZap((n) => n + 1);
  }
  const end = angleOf(value);
  const spark = score !== null && Math.abs(score) >= SPARK_SCORE && spec.glow;
  const description =
    score === null ? "Keine Daten" : `Score ${formatScore(score)} von minus 10 bis plus 10${label ? `, ${label}` : ""}`;
  const glow = spec.glow && score !== null ? `drop-shadow(0 0 var(--ring-glow) ${color})` : undefined;

  return (
    <div className={`relative inline-grid shrink-0 place-items-center ${spec.box} ${className ?? ""}`} role="img" aria-label={description}>
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full overflow-visible" aria-hidden="true">
        <path d={TRACK} fill="none" stroke="var(--c-track)" strokeWidth={spec.stroke} strokeLinecap="round" strokeDasharray={score === null ? "1 9" : undefined} />
        {score !== null && (
          <>
            <motion.path
              d={path}
              fill="none"
              strokeWidth={spec.stroke}
              strokeLinecap="round"
              style={{ stroke: color, transition: "stroke 240ms ease-out", filter: glow }}
            />
            {/* heller Kern des Energiebogens */}
            <motion.path
              d={path}
              fill="none"
              strokeWidth={spec.stroke * 0.3}
              strokeLinecap="round"
              style={{ stroke: CORE_COLOR[tone], opacity: 0.85 }}
            />
          </>
        )}
        {/* Nullmarke */}
        <line x1={tick.x} y1={tick.y - spec.stroke / 2 - 2.5} x2={tick.x} y2={tick.y - spec.stroke / 2 - 0.5} stroke="var(--c-ink-3)" strokeWidth={1.4} strokeLinecap="round" />
        {score !== null && zap > 0 && !reduced && (
          <path key={zap} d={boltPath(end, spec.stroke * 0.55)} pathLength={1} className="ring-bolt" strokeWidth={size === "sm" || size === "md" ? 2.2 : 1.8} />
        )}
        {spark && !reduced &&
          [0, 1, 2].map((i) => {
            const dir = (end > 0 ? 1 : -1) * (i - 1) * 38 + (end > 0 ? 40 : -40);
            const a = point(end, RADIUS + spec.stroke * 0.6);
            const dx = Math.cos((dir * Math.PI) / 180) * 7;
            const dy = -Math.sin((dir * Math.PI) / 180) * 7;
            return (
              <line
                key={i}
                className="ring-spark"
                x1={a.x}
                y1={a.y}
                x2={a.x + dx}
                y2={a.y + dy}
                strokeWidth={1.6}
                style={{ animationDelay: `${0.9 + i * 0.7}s` }}
              />
            );
          })}
      </svg>
      <div className="relative grid place-items-center text-center leading-none text-ink">
        {score === null ? (
          <span className={`${spec.number} text-ink-3`}>–</span>
        ) : (
          <span key={flash.n} className={flash.dir === "up" ? "flash-up" : flash.dir === "down" ? "flash-down" : undefined}>
            <MotionText value={spring} format={formatScore} className={spec.number} />
          </span>
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
