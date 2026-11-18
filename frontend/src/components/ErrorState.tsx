import type { ReactNode } from "react";

import { Card } from "./Card";
import { Button, EmptyState } from "./EmptyState";
import { IconWarning } from "./icons";

/** Fehlerzustand eines Abschnitts: sagt, was passiert ist, und bietet „Erneut laden“ an. */
export function ErrorState({ what, onRetry }: { what: string; onRetry: () => void }) {
  return (
    <Card>
      <EmptyState
        icon={<IconWarning size={26} />}
        title={`${what} konnten nicht geladen werden`}
        text="Der Server antwortet nicht. Prüfe die Verbindung und versuche es noch einmal."
        action={<Button onClick={onRetry}>Erneut laden</Button>}
      />
    </Card>
  );
}

/** Kleiner Leerzustand innerhalb einer Karte (kein Fehler): erklärt, warum nichts da ist. */
export function NoData({ title = "Keine Daten", text }: { title?: string; text: ReactNode }) {
  return (
    <div role="status" className="rounded-control bg-fill px-4 py-5 text-center">
      <p className="text-subhead font-semibold">{title}</p>
      <p className="mt-0.5 text-footnote text-ink-2">{text}</p>
    </div>
  );
}
