import { TERMS } from "../lib/glossary";
import { Sheet } from "./Sheet";
import { useUi } from "./ui-context";

/** Erklärung zu einer Kennzahl als Sheet (auch am Handy ohne Hover). */
export function ExplainSheet() {
  const { term, explain } = useUi();
  const entry = term ? TERMS[term] : null;
  return (
    <Sheet open={entry !== null} onOpenChange={(open) => !open && explain(null)} title={entry?.title ?? ""}>
      <div className="flex flex-col gap-3">
        {entry?.text.split("\n\n").map((paragraph) => (
          <p key={paragraph} className="text-body text-ink-2">
            {paragraph}
          </p>
        ))}
      </div>
    </Sheet>
  );
}
