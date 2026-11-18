import type { ReactNode } from "react";

import type { TermKey } from "../lib/glossary";
import { InfoTip } from "./InfoTip";

/** Abschnittsüberschrift innerhalb einer Seite: Titel, optional Erklärung und Platz für Schalter rechts. */
export function SectionTitle({ title, term, aside, id }: { title: string; term?: TermKey; aside?: ReactNode; id?: string }) {
  return (
    <div className="mb-3 flex min-h-9 flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <h2 id={id} className="flex items-center gap-1.5 text-title3 font-bold tracking-title">
        {title}
        {term && <InfoTip term={term} />}
      </h2>
      {aside}
    </div>
  );
}
