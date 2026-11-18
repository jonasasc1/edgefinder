import { TERMS } from "../lib/glossary";
import { Sheet } from "./Sheet";
import { useUi } from "./ui-context";

/** Erklärung zu einer Kennzahl als Sheet (auch am Handy ohne Hover). */
export function ExplainSheet() {
  const { term, explain } = useUi();
  const entry = term ? TERMS[term] : null;
  return (
    <Sheet open={entry !== null} onOpenChange={(open) => !open && explain(null)} title={entry?.title ?? ""}>
      <p className="text-body text-ink-2">{entry?.text}</p>
    </Sheet>
  );
}
