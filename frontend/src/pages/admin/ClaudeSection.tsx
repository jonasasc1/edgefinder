import { useCallback, useEffect, useState } from "react";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { MarkdownView } from "../../components/MarkdownView";
import { SectionTitle } from "../../components/SectionTitle";
import {
  AdminError,
  fetchClaudeAudit,
  fetchClaudeRun,
  fetchClaudeRuns,
  startClaudeRun,
  type AdminOverview,
} from "../../lib/api";
import {
  CLAUDE_GUIDE,
  CLAUDE_POLL_MS,
  STATE_LABEL,
  STATE_TONE,
  analysisFilename,
  auditSummary,
  availability,
  downloadText,
  durationText,
  filterAudit,
  isClaudeActive,
  shouldPollClaude,
  startInfo,
  stepOf,
  type AuditFilter,
  type ClaudeOverview,
  type ClaudeRun,
} from "../../lib/claudeLogic";
import { useApi } from "../../lib/useApi";
import { formatAgo, formatDateTime } from "../../lib/format";
import { useNow } from "./useAdminData";

const STEPS = ["Vorbereiten", "Wartet", "Läuft", "Fertig"];

function Steps({ run }: { run: ClaudeRun }) {
  const step = stepOf(run.state);
  const failed = run.state === "error" || run.state === "timeout" || run.state === "stale";
  return (
    <ol aria-label="Fortschritt" className="mt-2 flex gap-1">
      {STEPS.map((label, index) => {
        const reached = index + 1 <= step;
        const color = reached ? (failed && index + 1 === step ? "bg-bear-solid" : "bg-accent-solid") : "bg-fill";
        const pulse = isClaudeActive(run) && index + 1 === step ? "motion-safe:animate-pulse" : "";
        return (
          <li key={label} className="min-w-0 flex-1">
            <div aria-hidden="true" className={`h-1.5 rounded-chip ${color} ${pulse}`} />
            <span className={`mt-1 block truncate text-caption ${index + 1 === step ? "font-semibold text-ink" : "text-ink-2"}`}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function RunBadge({ run }: { run: ClaudeRun }) {
  return <Badge tone={STATE_TONE[run.state]}>{STATE_LABEL[run.state]}</Badge>;
}

function Notice({ o }: { o: ClaudeOverview }) {
  const state = availability(o);
  if (state === "ready") return null;
  return (
    <div role="status" className="rounded-control bg-fill p-3 text-footnote text-ink">
      <p className="font-semibold">{state === "disabled" ? "Der Claude-Prüfagent ist noch nicht aktiviert." : "Der Claude-Prüfagent ist noch nicht installiert."}</p>
      <p className="mt-1 text-ink-2">
        Er wird einmalig auf dem Server eingerichtet und mit deinem Abo angemeldet; erst dann wird <code>claude.enabled</code> eingeschaltet. Schritt-für-Schritt-Anleitung: <code>{CLAUDE_GUIDE}</code> (Abschnitt „Claude-Prüfagent“ in der README).
      </p>
    </div>
  );
}

type Tab = "ergebnis" | "vorschlaege" | "protokoll";
const TABS: { key: Tab; label: string }[] = [
  { key: "ergebnis", label: "Ergebnis" },
  { key: "vorschlaege", label: "Vorschläge" },
  { key: "protokoll", label: "Protokoll" },
];
const FILTERS: { key: AuditFilter; label: string }[] = [
  { key: "all", label: "Alles" },
  { key: "tools", label: "Werkzeuge" },
  { key: "denied", label: "Abgelehnt" },
  { key: "errors", label: "Fehler" },
];
const PAGE = 100; // Einträge je Seite des Protokolls

function AuditView({ id }: { id: number }) {
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<AuditFilter>("all");
  const { state, reload } = useApi((signal) => fetchClaudeAudit(id, offset, PAGE, signal), [id, offset]);
  const page = state.status === "ready" ? state.data : null;
  const shown = page ? filterAudit(page.entries, filter) : [];
  const pages = page ? Math.max(1, Math.ceil(page.total / PAGE)) : 1;
  return (
    <div>
      <div role="group" aria-label="Protokoll filtern" className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            aria-pressed={filter === f.key}
            onClick={() => setFilter(f.key)}
            className={`min-h-touch rounded-control px-3 text-footnote font-semibold ${filter === f.key ? "bg-accent-solid text-on-accent" : "bg-fill text-ink"}`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <p aria-live="polite" className="mt-2 text-caption text-ink-2">
        {state.status === "loading" && "Lädt …"}
        {state.status === "error" && state.message}
        {page && `Seite ${offset / PAGE + 1} von ${pages}; ${shown.length} von ${page.entries.length} Einträgen dieser Seite (insgesamt ${page.total}).`}
      </p>
      {state.status === "error" && (
        <button type="button" onClick={reload} className="mt-2 h-touch rounded-control bg-fill px-4 text-subhead font-semibold text-ink">
          Erneut laden
        </button>
      )}
      {page && shown.length === 0 && <p className="mt-2 text-footnote text-ink-2">Keine Einträge für diesen Filter.</p>}
      <ol aria-label="Werkzeugaufrufe" className="mt-2 space-y-1.5">
        {shown.map((entry, index) => (
          <li key={index} className={`rounded-control p-2 text-caption ${entry.decision === "deny" ? "bg-bear-soft text-bear-ink" : "bg-fill text-ink"}`}>
            <div className="flex flex-wrap items-center gap-x-2 text-ink-2">
              {entry.t && <time dateTime={entry.t}>{entry.t.slice(11, 19)}</time>}
              <span>{entry.event === "PreToolUse" ? "Aufruf" : entry.event === "PostToolUse" ? "Ergebnis" : (entry.event ?? "")}</span>
              {entry.tool && <strong className="text-ink">{entry.tool}</strong>}
            </div>
            <p className="mt-0.5 whitespace-pre-wrap break-words font-mono">{auditSummary(entry)}</p>
          </li>
        ))}
      </ol>
      {pages > 1 && (
        <div className="mt-3 flex gap-2">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} className="h-touch rounded-control bg-fill px-4 text-subhead font-semibold text-ink disabled:text-ink-2">
            Zurück
          </button>
          <button type="button" disabled={offset + PAGE >= (page?.total ?? 0)} onClick={() => setOffset(offset + PAGE)} className="h-touch rounded-control bg-fill px-4 text-subhead font-semibold text-ink disabled:text-ink-2">
            Weiter
          </button>
        </div>
      )}
    </div>
  );
}

function RunDetail({ id, state }: { id: number; state: ClaudeRun["state"] }) {
  const { state: loaded } = useApi((signal) => fetchClaudeRun(id, signal), [id, state]);
  const [tab, setTab] = useState<Tab>("ergebnis");
  const error = loaded.status === "error" ? loaded.message : null;
  const detail = loaded.status === "ready" ? loaded.data : null;

  if (error) return <p role="alert" className="mt-3 text-footnote text-bear-ink">{error}</p>;
  if (!detail) return <p role="status" className="mt-3 text-footnote text-ink-2">Lädt …</p>;
  return (
    <div className="mt-3 border-t border-line pt-3">
      <div role="tablist" aria-label="Ansicht" className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`claude-tab-${t.key}`}
            aria-selected={tab === t.key}
            aria-controls={`claude-panel-${t.key}`}
            onClick={() => setTab(t.key)}
            className={`min-h-touch whitespace-nowrap rounded-control px-2.5 text-footnote font-semibold ${tab === t.key ? "bg-accent-solid text-on-accent" : "bg-fill text-ink"}`}
          >
            {t.label}
            {t.key === "vorschlaege" && detail.proposals.length > 0 ? ` (${detail.proposals.length})` : ""}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`claude-panel-${tab}`} aria-labelledby={`claude-tab-${tab}`} className="mt-3">
        {tab === "ergebnis" &&
          (detail.analysis_md ? (
            <>
              <button type="button" onClick={() => downloadText(analysisFilename(id), detail.analysis_md ?? "")} className="h-touch rounded-control bg-fill px-4 text-subhead font-semibold text-ink hover:bg-fill-strong">
                Download analysis.md
              </button>
              <MarkdownView source={detail.analysis_md} />
            </>
          ) : (
            <p className="text-footnote text-ink-2">{detail.message ?? (isClaudeActive(detail) ? "Noch kein Ergebnis – die Analyse läuft." : "Keine analysis.md vorhanden.")}</p>
          ))}
        {tab === "vorschlaege" &&
          (detail.proposals.length ? (
            detail.proposals.map((p) => (
              <div key={p.name} className="mb-3">
                <h4 className="text-subhead font-semibold">{p.name}</h4>
                <p className="text-caption text-ink-2">Reiner Textvorschlag; nichts wurde eingespielt.</p>
                <pre tabIndex={0} aria-label={`Vorschlag ${p.name}`} className="mt-1 max-h-80 overflow-auto whitespace-pre rounded-control bg-fill p-3 text-caption text-ink">
                  {p.text}
                </pre>
              </div>
            ))
          ) : (
            <p className="text-footnote text-ink-2">Keine Vorschlagsdateien. Textvorschläge stehen in der Analyse.</p>
          ))}
        {tab === "protokoll" && (detail.has_audit ? <AuditView id={id} /> : <p className="text-footnote text-ink-2">Noch kein Protokoll vorhanden.</p>)}
      </div>
    </div>
  );
}

function RunItem({ run, open, onToggle }: { run: ClaudeRun; open: boolean; onToggle: () => void }) {
  const duration = durationText(run.duration_seconds);
  const when = run.finished_at ?? run.started_at ?? run.created_at ?? run.requested_at;
  return (
    <li className="rounded-control ring-1 ring-edge">
      <button type="button" aria-expanded={open} onClick={onToggle} className="flex min-h-touch w-full flex-wrap items-center justify-between gap-2 p-3 text-left">
        <span className="min-w-0">
          <span className="text-subhead font-semibold">Analyse #{run.id}</span>
          <span className="block text-caption text-ink-2">
            <time dateTime={when}>{formatDateTime(when)}</time> ({formatAgo(when)}){duration ? `, Dauer ${duration}` : ""}
            {run.turns ? `, ${run.turns} Schritte` : ""}
          </span>
        </span>
        <RunBadge run={run} />
      </button>
      <div className="px-3 pb-3">
        {isClaudeActive(run) && <Steps run={run} />}
        {run.message && <p className={`mt-1 text-footnote ${run.state === "ok" ? "text-ink-2" : "font-medium text-bear-ink"}`}>{run.message}</p>}
        {open && <RunDetail id={run.id} state={run.state} />}
      </div>
    </li>
  );
}

export function ClaudeSection({ overview, reload }: { overview: AdminOverview; reload: () => Promise<void> }) {
  const first = useApi((signal) => fetchClaudeRuns(signal), []);
  const [mountedAt] = useState(() => Date.now());
  const [fresh, setFresh] = useState<{ overview: ClaudeOverview; runs: ClaudeRun[]; loadedAt: number } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [hidden, setHidden] = useState(() => document.hidden);

  const load = useCallback(async () => {
    try {
      const result = await fetchClaudeRuns();
      setFresh({ ...result, loadedAt: Date.now() });
      setLoadError(null);
    } catch (e) {
      setLoadError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    const onVisibility = () => {
      setHidden(document.hidden);
      if (!document.hidden) void load();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [load]);

  const data = fresh ?? (first.state.status === "ready" ? { ...first.state.data, loadedAt: mountedAt } : null);
  const error = loadError ?? (first.state.status === "error" && !fresh ? first.state.message : null);
  const runs = data?.runs ?? [];
  const polling = shouldPollClaude(runs, hidden);
  useEffect(() => {
    if (!polling) return;
    const id = window.setInterval(() => void load(), CLAUDE_POLL_MS);
    return () => window.clearInterval(id);
  }, [polling, load]);

  const o = data?.overview ?? overview.claude;
  const now = useNow(o.wait_seconds > 0);
  const wait = Math.max(0, o.wait_seconds - (data ? Math.max(0, now - data.loadedAt) / 1000 : 0));
  const info = startInfo(o, wait, busy);

  const start = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const job = await startClaudeRun();
      setOpenId(job.id);
      setMessage({ text: "Analyse eingereiht. Zuerst wird das Eingabepaket gebaut, dann startet Claude (einige Minuten).", error: false });
    } catch (e) {
      setMessage({ text: (e as AdminError).message, error: true });
    } finally {
      setBusy(false);
      await load();
      await reload();
    }
  };

  return (
    <section aria-labelledby="claude-title">
      <SectionTitle title="Claude-Analyse" id="claude-title" />
      <Card className="p-4 sm:p-5">
        <p className="text-subhead text-ink-2">
          Ein abgeschotteter Claude-Agent prüft Datenzuverlässigkeit, Bilanz und Fehlerbild auf einer Kopie der Daten und macht <strong className="text-ink">nur Vorschläge</strong>. Er ändert nichts, hat keinen Zugriff auf andere Server und kann nichts kaufen oder verkaufen. Jeder Schritt wird protokolliert. Dauer: einige Minuten; sie zählt zum Nutzungslimit deines Abos.
        </p>
        <div className="mt-3">
          <Notice o={o} />
        </div>
        <button
          type="button"
          disabled={!info.canStart}
          onClick={() => void start()}
          className="mt-3 h-touch w-full rounded-control bg-accent-solid px-4 text-subhead font-semibold text-on-accent disabled:bg-fill disabled:text-ink-2 sm:w-auto"
        >
          {o.active_id !== null || busy ? "Analyse läuft" : "Claude-Analyse starten"}
        </button>
        <p className="mt-2 text-caption text-ink-2">
          {info.reason ?? "Bereit."} Heute {o.runs_today} von {o.max_runs_per_day} Analysen (rollierend 24 h), Abkühlzeit {o.cooldown_minutes} Min., höchstens {o.max_turns} Schritte, Läufe bleiben {o.retention_days} Tage gespeichert.
        </p>
        <div aria-live="polite">
          {message && (
            <p role={message.error ? "alert" : "status"} className={`mt-3 rounded-control px-3 py-2 text-footnote ${message.error ? "bg-bear-soft text-bear-ink" : "bg-fill text-ink"}`}>
              {message.text}
            </p>
          )}
        </div>
        {error && <p role="alert" className="mt-3 text-footnote text-bear-ink">{error}</p>}
        {runs.length > 0 && (
          <ul aria-label="Bisherige Analysen" className="mt-4 space-y-2">
            {runs.map((run) => (
              <RunItem key={run.id} run={run} open={openId === run.id} onToggle={() => setOpenId(openId === run.id ? null : run.id)} />
            ))}
          </ul>
        )}
        {data && runs.length === 0 && <p className="mt-4 text-footnote text-ink-2">Noch keine Analyse gestartet.</p>}
      </Card>
    </section>
  );
}
