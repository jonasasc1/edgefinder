import { useId } from "react";

/*
 * Bildmarke von E-Giant: eine Panzerplatte (zwei abgeschrägte Ecken) mit einem monumentalen „E“,
 * dessen mittlerer Arm ein Blitz ist. Selbst gezeichnet, 32×32. Farben aus den Marken-Tokens
 * (--c-mark-*, --c-volt); die Geometrie steht hier und in scripts/make-icons.mjs / public/favicon.svg.
 */
export const MARK_PLATE = "M9 1.5H30.5V23L23 30.5H1.5V9Z";
export const MARK_E = "M8 7H24.5V10.4H11.5V21.6H24.5V25H8Z";
export const MARK_BOLT = "M11.5 13.7H19L17 15.7H24.5L15.5 21.4 18.2 17.1H11.5Z";

type MarkProps = { size?: number; className?: string; /** Teile einzeln animierbar (Intro) */ parts?: boolean };

export function BrandMark({ size = 28, className, parts = false }: MarkProps) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false" className={className}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--c-mark-a)" />
          <stop offset="1" stopColor="var(--c-mark-b)" />
        </linearGradient>
      </defs>
      <path
        d={MARK_PLATE}
        pathLength={1}
        className={parts ? "intro-plate" : undefined}
        fill="var(--c-mark-plate)"
        stroke="var(--c-arc)"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      <path d={MARK_E} fill={`url(#${id})`} className={parts ? "intro-e" : undefined} />
      <path d={MARK_BOLT} fill="var(--c-volt)" transform="translate(0 -0.6)" className={parts ? "intro-bolt" : undefined} />
    </svg>
  );
}

/** Slogan der Marke: Giant = groß denken, Elektro = Strom. */
export const SLOGAN = "Groß denken. Unter Strom.";

/** Slogan als ruhige Zeile (kleine Saira, Versalien-frei, weit gesetzt); Farbe `ink-2` (AA). */
export function Slogan({ className }: { className?: string }) {
  return <span className={`block font-display text-[0.6875rem] font-medium leading-tight tracking-[0.06em] text-ink-2 ${className ?? ""}`}>{SLOGAN}</span>;
}

/** Wortmarke: Bildmarke + „E-Giant“ in Saira (Versalien, weit gesetzt); optional mit Slogan darunter. */
export function Wordmark({ size = 28, className, slogan = false }: { size?: number; className?: string; slogan?: boolean }) {
  const word = (
    <span className="block font-display font-extrabold uppercase leading-none tracking-wider" style={{ fontSize: size * 0.72 }}>
      E-Giant
    </span>
  );
  return (
    <span className={`inline-flex items-center gap-2.5 ${className ?? ""}`}>
      <BrandMark size={size} />
      {slogan ? (
        <span className="flex min-w-0 flex-col gap-1">
          {word}
          <Slogan />
        </span>
      ) : (
        word
      )}
    </span>
  );
}
