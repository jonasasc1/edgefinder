import type { ReactNode } from "react";

import type { Tone } from "../lib/score";

const TONE: Record<Tone, string> = {
  "bull-strong": "bg-bull-solid text-on-solid",
  bull: "bg-bull-soft text-bull-ink",
  flat: "bg-flat-soft text-flat-ink",
  bear: "bg-bear-soft text-bear-ink",
  "bear-strong": "bg-bear-solid text-on-solid",
};

/** Kapsel-Label. Stärke zeigt sich über Füllung: weich = Bullish/Bearish, gefüllt = Stark. */
export function Badge({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-chip px-2.5 py-0.5 text-caption font-semibold ${TONE[tone]} ${className ?? ""}`}
    >
      {children}
    </span>
  );
}

/** Neutrales Etikett (Assetklasse u. Ä.) ohne Signalfarbe. */
export function Tag({ children }: { children: ReactNode }) {
  return <span className="text-caption font-medium text-ink-2">{children}</span>;
}
