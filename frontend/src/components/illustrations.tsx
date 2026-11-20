import type { ReactNode } from "react";

/*
 * Illustrationen für Leer-, Fehler- und Offline-Zustände: eigene Strichzeichnungen im Stil der
 * Marke (Panzerplatte, Blitz, Pole mit Lichtbogen). Farben nur aus Tokens; Funken atmen langsam
 * (ruhend bei reduzierter Bewegung). Dekorativ: aria-hidden, der Text trägt die Information.
 */

export type ArtKind = "offline" | "error" | "miss" | "empty";

function Frame({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 160 120" width="160" height="120" aria-hidden="true" focusable="false" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5">
      {children}
    </svg>
  );
}

/** Riese mit leerer Batterie: Panzerplatte als Akku, nur eine Zelle glimmt noch. */
function Offline() {
  return (
    <Frame>
      <path d="M32 38H118V84L106 96H32Z" stroke="var(--c-arc)" fill="var(--c-surface)" />
      <path d="M118 56h8v20h-8" stroke="var(--c-arc)" />
      <path d="M40 48h14v38H40Z" stroke="var(--c-volt-ink)" fill="var(--c-volt-soft)" strokeWidth="2" />
      <path d="M62 48h14v38H62Zm22 0h14v38H84Z" stroke="var(--c-ink-3)" strokeDasharray="3 5" strokeWidth="2" />
      <path d="M78 12 66 32h10l-4 14 14-20H76Z" stroke="var(--c-ink-3)" strokeDasharray="3 4" strokeWidth="2" />
      <path d="M20 106h120" stroke="var(--c-line)" />
    </Frame>
  );
}

/** Blitz getrennt: ein Blitz, in der Mitte gekappt, an der Bruchstelle sprühen Funken. */
function ErrorArt() {
  return (
    <Frame>
      <path d="M86 8 52 58h26l8-12" stroke="var(--c-volt-ink)" fill="var(--c-volt-soft)" />
      <path d="M90 74 70 112l38-44H86" stroke="var(--c-ink-3)" fill="var(--c-fill)" />
      <path className="art-spark" d="M104 52l10-8M110 62l12-1M98 44l3-12" stroke="var(--c-arc)" strokeWidth="2.5" />
      <path className="art-spark" style={{ animationDelay: "0.9s" }} d="M64 70l-10 6M70 80l-12 6" stroke="var(--c-arc)" strokeWidth="2.5" />
    </Frame>
  );
}

/** Blitz ins Leere: der Strahl geht ins Nichts, am Boden bleibt nur ein gestrichelter Kreis. */
function Miss() {
  return (
    <Frame>
      <path d="M92 6 66 52h22l-10 38 34-48H92l8-36Z" stroke="var(--c-volt-ink)" fill="var(--c-volt-soft)" />
      <ellipse cx="82" cy="102" rx="34" ry="8" stroke="var(--c-arc)" strokeDasharray="4 5" strokeWidth="2" />
      <path className="art-spark" d="M50 96l-8-4M114 96l8-4M82 88v-6" stroke="var(--c-arc)" strokeWidth="2.5" />
    </Frame>
  );
}

/** Zwei Pole, dazwischen noch kein Strom: gestrichelter Bogen, ein dunkler Funke. */
function Empty() {
  return (
    <Frame>
      <path d="M34 98V54l-6-8h24l-6 8v44Z" stroke="var(--c-arc)" fill="var(--c-surface)" />
      <path d="M126 98V54l-6-8h24l-6 8v44Z" stroke="var(--c-arc)" fill="var(--c-surface)" transform="translate(-24 0)" />
      <path d="M52 46C66 16 94 16 108 46" stroke="var(--c-ink-3)" strokeDasharray="3 6" strokeWidth="2" />
      <path d="M74 36h14l-4 10 10-1-14 16 3-12h-11Z" stroke="var(--c-volt-ink)" fill="var(--c-volt-soft)" strokeWidth="2" />
      <path d="M22 106h116" stroke="var(--c-line)" />
    </Frame>
  );
}

/** Bei fehlender Verbindung die Offline-Illustration (leere Batterie), sonst die Fehler-Illustration (Blitz getrennt). */
export const connectionArt = (): ArtKind => (navigator.onLine === false ? "offline" : "error");

export function Illustration({ kind }: { kind: ArtKind }) {
  return kind === "offline" ? <Offline /> : kind === "error" ? <ErrorArt /> : kind === "miss" ? <Miss /> : <Empty />;
}
