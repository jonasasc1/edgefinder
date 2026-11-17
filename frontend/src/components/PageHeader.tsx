import type { ReactNode } from "react";

/** Seitenkopf mit großem iOS-Titel; `actions` sitzt rechts neben dem Titel. */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex items-end justify-between gap-4 px-4 pb-4 pt-[max(1.25rem,env(safe-area-inset-top))] sm:px-8 lg:pt-10">
      <div className="min-w-0">
        <h1 className="text-largetitle font-bold tracking-title">{title}</h1>
        {subtitle && <p className="mt-1 text-subhead text-ink-2">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}
