import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { SectionTitle } from "../../components/SectionTitle";
import type { AdminOverview, AdminRun } from "../../lib/api";
import { formatAgo, formatDate, formatDateTime, formatHours } from "../../lib/format";
import { sourceLabel } from "../../lib/glossary";
import type { Tone } from "../../lib/score";

function runState(run: AdminRun): { label: string; tone: Tone; problem: boolean } {
  if (!run.last_success) return { label: "Noch nie erfolgreich", tone: "bear", problem: true };
  if (run.stale) return { label: "Veraltet", tone: "bear", problem: true };
  if (run.last_run_status === "error") return { label: "Letzter Lauf fehlgeschlagen", tone: "bear", problem: true };
  if (run.last_run_status === "partial") return { label: "Teilweise Lücken", tone: "flat", problem: false };
  return { label: "Aktuell", tone: "bull", problem: false };
}

export function SystemSection({ overview }: { overview: AdminOverview }) {
  const now = new Date(overview.now);
  const runs = [...overview.runs].sort((a, b) => Number(runState(b).problem) - Number(runState(a).problem));
  const { calibration: cal, live } = overview;
  const fact = (label: string, value: string) => (
    <div className="min-w-0">
      <dt className="text-caption text-ink-2">{label}</dt>
      <dd className="num text-subhead font-semibold">{value}</dd>
    </div>
  );
  return (
    <section aria-labelledby="system-title">
      <SectionTitle title="Systemzustand" id="system-title" />
      <Card className="p-4 sm:p-5">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          {fact("Modellversion", overview.model_version)}
          {fact("Letzte Scores", overview.last_score_date ? formatDate(overview.last_score_date) : "–")}
          {fact("Eichung bis", cal.available && cal.data_through ? formatDate(cal.data_through) : "keine Eichung")}
          {fact("Live seit", live.live_since ? formatDate(live.live_since) : "–")}
          {fact("Ausgewertet", live.evaluated === null ? "–" : String(live.evaluated))}
          {fact("Offen", live.open === null ? "–" : String(live.open))}
          {fact("Eichung erzeugt", cal.generated_at ? formatDateTime(cal.generated_at) : "–")}
          {fact("Fortschritt", live.progress === null ? "–" : `${Math.round(live.progress * 100)} %`)}
        </dl>
        <ul className="mt-4 divide-y divide-line border-t border-line">
          {runs.map((run) => {
            const state = runState(run);
            return (
              <li key={run.source} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2.5">
                <div className="min-w-0">
                  <p className="text-subhead font-medium">{sourceLabel(run.source)}</p>
                  <p className="text-caption text-ink-2">
                    {run.last_run_at ? `Letzter Lauf ${formatAgo(run.last_run_at, now)}` : "Noch kein Lauf"}
                    {run.last_success ? `, zuletzt erfolgreich ${formatAgo(run.last_success, now)}` : ""} (veraltet nach {formatHours(run.stale_after_hours)})
                  </p>
                  {state.problem && run.last_error && <p className="mt-0.5 break-words text-caption text-bear-ink">{run.last_error}</p>}
                </div>
                <Badge tone={state.tone}>{state.label}</Badge>
              </li>
            );
          })}
        </ul>
      </Card>
    </section>
  );
}
