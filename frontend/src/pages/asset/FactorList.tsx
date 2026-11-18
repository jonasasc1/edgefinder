import { useState } from "react";

import { Badge } from "../../components/Badge";
import { InfoTip } from "../../components/InfoTip";
import { ScoreBar, toneOfSubscore } from "../../components/ScoreBar";
import type { Component, ProfileDetail } from "../../lib/api";
import { formatDelta, formatDecimal, formatPercent } from "../../lib/format";
import { FACTORS, factorLabel } from "../../lib/glossary";

const TEXT_TONE = {
  "bull-strong": "text-bull-ink",
  bull: "text-bull-ink",
  flat: "text-ink-2",
  bear: "text-bear-ink",
  "bear-strong": "text-bear-ink",
} as const;

const SUBSCORE_WORD: Record<string, string> = {
  "bull-strong": "stark bullish",
  bull: "bullish",
  flat: "neutral",
  bear: "bearish",
  "bear-strong": "stark bearish",
};

/** Beitrag zum Gesamtscore in Punkten (Teilscore × effektives Gewicht × 10). */
export const contributionOf = (component: Component) => (component.subscore ?? 0) * component.effective_weight * 10;

function Reason({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 150;
  return (
    <div className="mt-2">
      <p className={`text-footnote text-ink-2 ${long && !open ? "line-clamp-2" : ""}`}>{text}</p>
      {long && (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="mt-0.5 min-h-6 text-footnote font-medium text-accent-ink">
          {open ? "Weniger" : "Ganze Begründung"}
        </button>
      )}
    </div>
  );
}

function Factor({ component }: { component: Component }) {
  const { factor, subscore, weight, effective_weight } = component;
  const entry = FACTORS[factor];
  const available = subscore !== null;
  const tone = available ? toneOfSubscore(subscore) : "flat";
  const contribution = contributionOf(component);
  return (
    <li className="px-4 py-3.5 sm:px-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-1.5 text-body font-semibold tracking-tight">
          {factorLabel(factor)}
          {entry?.term && <InfoTip term={entry.term} />}
        </h3>
        {available ? (
          <span className={`num text-body font-semibold ${TEXT_TONE[tone]}`}>
            <span className="sr-only">Beitrag </span>
            {formatDelta(contribution)}
          </span>
        ) : (
          <Badge tone="flat">Keine Daten</Badge>
        )}
      </div>
      <div className="mt-2.5 flex items-center gap-3">
        <ScoreBar value={subscore} />
        <span className="num w-12 shrink-0 text-right text-footnote font-medium text-ink-2">
          {available ? formatDecimal(subscore, 2) : "–"}
        </span>
      </div>
      <p className="mt-1.5 text-caption text-ink-2">
        {available ? (
          <>
            Teilscore {formatDecimal(subscore, 2)} ({SUBSCORE_WORD[tone]}) · Gewicht {formatPercent(effective_weight)}
            {Math.abs(effective_weight - weight) > 0.005 && ` (laut Profil ${formatPercent(weight)})`}
          </>
        ) : (
          <>Gewicht {formatPercent(weight)} entfällt, die übrigen Faktoren zählen entsprechend mehr.</>
        )}
      </p>
      <Reason text={component.reason} />
    </li>
  );
}

/** Teilscores mit Balken, Gewicht, Beitrag und der deutschen Begründung der Score-Engine. */
export function FactorList({ detail }: { detail: ProfileDetail }) {
  return (
    <ul className="divide-y divide-line">
      {detail.components.map((component) => (
        <Factor key={component.factor} component={component} />
      ))}
    </ul>
  );
}
