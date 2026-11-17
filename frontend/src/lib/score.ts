// Bedeutung eines Scores: Stärkestufe (−2 … +2) und die dazugehörigen Token-Namen.
// Schwellen stehen in config.yaml (scoring.labels); die API liefert das Label mit.

export const SCORE_MIN = -10;
export const SCORE_MAX = 10;

export type Level = -2 | -1 | 0 | 1 | 2;
export type Tone = "bull" | "bull-strong" | "bear" | "bear-strong" | "flat";

const LABEL_LEVEL: Record<string, Level> = {
  "Stark bullish": 2,
  Bullish: 1,
  Neutral: 0,
  Bearish: -1,
  "Stark bearish": -2,
};

export function levelOf(score: number, label?: string): Level {
  const fromLabel = label ? LABEL_LEVEL[label] : undefined;
  if (fromLabel !== undefined) return fromLabel;
  if (score >= 6) return 2;
  if (score >= 2) return 1;
  if (score > -2) return 0;
  if (score > -6) return -1;
  return -2;
}

export function toneOf(level: Level): Tone {
  if (level === 2) return "bull-strong";
  if (level === 1) return "bull";
  if (level === -1) return "bear";
  if (level === -2) return "bear-strong";
  return "flat";
}

/** CSS-Variable der Ringfarbe zu einer Stufe (Tokens aus design/tokens.css). */
export const RING_COLOR: Record<Tone, string> = {
  "bull-strong": "var(--c-bull-ring-strong)",
  bull: "var(--c-bull-ring)",
  flat: "var(--c-flat-ring)",
  bear: "var(--c-bear-ring)",
  "bear-strong": "var(--c-bear-ring-strong)",
};

export const clampScore = (score: number) => Math.min(SCORE_MAX, Math.max(SCORE_MIN, score));
