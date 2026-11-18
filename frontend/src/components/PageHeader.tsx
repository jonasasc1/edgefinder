import type { ReactNode } from "react";

import { IconSearch } from "./icons";
import { useUi } from "./ui-context";

/** Suche (Command-Palette) – auf jeder Seite im Kopf erreichbar, am Handy der einzige Weg dorthin. */
export function SearchButton() {
  const { setPaletteOpen } = useUi();
  return (
    <button
      type="button"
      onClick={() => setPaletteOpen(true)}
      aria-label="Suchen und navigieren"
      aria-keyshortcuts="Control+K Meta+K"
      className="grid size-touch shrink-0 place-items-center rounded-chip bg-surface text-ink-2 shadow-card ring-1 ring-edge"
    >
      <IconSearch size={20} />
    </button>
  );
}

/** Seitenkopf mit großem iOS-Titel; `actions` sitzt rechts neben dem Titel. */
export function PageHeader({ title, subtitle, actions, before }: { title: string; subtitle?: ReactNode; actions?: ReactNode; before?: ReactNode }) {
  return (
    <header className="px-4 pb-4 pt-[max(1.25rem,env(safe-area-inset-top))] sm:px-8 lg:pt-10">
      {before}
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-largetitle font-bold tracking-title">{title}</h1>
          {subtitle && <p className="mt-1 text-subhead text-ink-2">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          <SearchButton />
        </div>
      </div>
    </header>
  );
}
