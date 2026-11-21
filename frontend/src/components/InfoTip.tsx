import { TERMS, type TermKey } from "../lib/glossary";
import { IconInfo } from "./icons";
import { Tooltip } from "./Tooltip";
import { useUi } from "./ui-context";

/** Kleines „i“ neben einer Kennzahl: Hover/Fokus zeigt den Kurztext, Tippen öffnet die Erklärung. */
export function InfoTip({ term }: { term: TermKey }) {
  const { explain } = useUi();
  const { title, text } = TERMS[term];
  return (
    <Tooltip content={<span>{text.split("\n\n")[0]}</span>}>
      <button
        type="button"
        onClick={() => explain(term)}
        aria-label={`Erklärung: ${title}`}
        className="-my-1 inline-grid size-6 shrink-0 place-items-center rounded-chip text-ink-2 hover:text-ink"
      >
        <IconInfo size={16} />
      </button>
    </Tooltip>
  );
}
