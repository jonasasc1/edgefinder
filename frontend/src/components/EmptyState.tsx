import type { ReactNode } from "react";

/** Leer-/Fehlerzustand: Icon, ein Satz, was passiert ist, und eine Handlung. */
export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text: string; action?: ReactNode }) {
  return (
    <div role="status" className="mx-auto flex max-w-sm flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 grid size-14 place-items-center rounded-chip bg-fill text-ink-2">{icon}</div>
      <h2 className="text-title3 font-bold tracking-title">{title}</h2>
      <p className="mt-1.5 text-subhead text-ink-2">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Primäre Schaltfläche (Bedienfarbe Blau). */
export function Button({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-touch rounded-chip bg-accent-solid px-6 text-subhead font-semibold text-on-accent active:opacity-80"
    >
      {children}
    </button>
  );
}
