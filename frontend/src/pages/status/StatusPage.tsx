import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { ErrorState } from "../../components/ErrorState";
import { IconStatus, IconWarning } from "../../components/icons";
import { PageHeader } from "../../components/PageHeader";
import { Skeleton } from "../../components/Skeleton";
import { fetchStatus, type SourceStatus, type Status } from "../../lib/api";
import { formatAgo, formatDateMedium, formatDateTime, formatHours } from "../../lib/format";
import { SOURCES, sourceLabel } from "../../lib/glossary";
import { useApi } from "../../lib/useApi";
import { HEALTH, healthOf, JOB_SOURCES, sortSources } from "./model";

function Summary({ status }: { status: Status }) {
  const problems = status.sources.filter((s) => !JOB_SOURCES.includes(s.source) && HEALTH[healthOf(s)].problem);
  const jobProblems = status.sources.filter((s) => JOB_SOURCES.includes(s.source) && HEALTH[healthOf(s)].problem);
  const ok = problems.length === 0;
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start gap-4">
        <div className={`grid size-12 shrink-0 place-items-center rounded-chip ${ok ? "bg-bull-soft text-bull-ink" : "bg-bear-soft text-bear-ink"}`}>
          {ok ? <IconStatus size={24} /> : <IconWarning size={24} />}
        </div>
        <div className="min-w-0">
          <h2 className="text-title3 font-bold tracking-title">
            {ok ? "Alle Datenquellen sind aktuell" : problems.length === 1 ? "Eine Datenquelle ist nicht aktuell" : `${problems.length} Datenquellen sind nicht aktuell`}
          </h2>
          <p className="mt-1 text-subhead text-ink-2">
            {ok
              ? "Die Scores beruhen auf frischen Daten."
              : `Scores, die auf ${problems.map((s) => sourceLabel(s.source)).join(", ")} beruhen, nutzen ältere Werte oder lassen den Faktor weg (Abdeckung sinkt).`}
          </p>
          {jobProblems.length > 0 && (
            <p className="mt-2 text-footnote text-ink-2">
              {jobProblems.map((s) => sourceLabel(s.source)).join(" und ")}: zuletzt nicht erfolgreich oder noch nicht gelaufen. Das betrifft nur Bilanz und Eichung, nicht die Scores.
            </p>
          )}
          <p className="mt-2 text-footnote text-ink-2">
            {status.last_score_date
              ? `Letzte Score-Berechnung für ${formatDateMedium(status.last_score_date)}${status.last_scored_at ? ` (berechnet ${formatAgo(status.last_scored_at, new Date(status.now))})` : ""}`
              : "Es wurde noch kein Score berechnet."}
          </p>
        </div>
      </div>
    </Card>
  );
}

function SourceRow({ source, now }: { source: SourceStatus; now: Date }) {
  const health = healthOf(source);
  const { label, tone, problem } = HEALTH[health];
  const info = SOURCES[source.source];
  return (
    <li className="px-4 py-4 sm:px-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-body font-semibold tracking-tight">{sourceLabel(source.source)}</h3>
          {info && <p className="mt-0.5 text-footnote text-ink-2">{info.text}</p>}
        </div>
        <Badge tone={tone} className="shrink-0">{label}</Badge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-footnote">
        <dt className="text-ink-2">Letzte Aktualisierung</dt>
        <dd className="num text-right font-medium">
          {source.last_success ? (
            <>
              {formatAgo(source.last_success, now)}
              <span className="block text-caption font-normal text-ink-2">{formatDateTime(source.last_success)}</span>
            </>
          ) : (
            "noch nie"
          )}
        </dd>
        <dt className="text-ink-2">Gilt als veraltet nach</dt>
        <dd className="num text-right font-medium">{formatHours(source.stale_after_hours)}</dd>
      </dl>
      {problem && (
        <p className="mt-3 rounded-control bg-bear-soft px-3 py-2 text-footnote text-bear-ink">
          {health === "stale" && `Die letzte erfolgreiche Aktualisierung ist älter als ${formatHours(source.stale_after_hours)}. `}
          {health === "never" && "Diese Quelle wurde noch nicht erfolgreich abgerufen. "}
          {source.last_error && <span className="block text-ink-2">Meldung der Quelle: {source.last_error}</span>}
        </p>
      )}
    </li>
  );
}

export function StatusPage() {
  const { state, reload } = useApi((signal) => fetchStatus(signal), []);
  return (
    <>
      <PageHeader title="Status" subtitle="Wie aktuell sind die Daten?" />
      <div className="flex flex-col gap-4 px-4 sm:px-8">
        {state.status === "loading" && (
          <div aria-busy="true" aria-label="Lädt" className="flex flex-col gap-4">
            <Skeleton className="h-36 w-full rounded-card" />
            <Skeleton className="h-96 w-full rounded-card" />
          </div>
        )}
        {state.status === "error" && <ErrorState what="Der Status" onRetry={reload} />}
        {state.status === "ready" && (
          <>
            <Summary status={state.data} />
            <Card variant="group">
              <ul className="divide-y divide-line">
                {sortSources(state.data.sources).map((source) => (
                  <SourceRow key={source.source} source={source} now={new Date(state.data.now)} />
                ))}
              </ul>
            </Card>
          </>
        )}
      </div>
    </>
  );
}
