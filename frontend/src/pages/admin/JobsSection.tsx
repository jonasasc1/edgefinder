import { useState } from "react";

import * as Dialog from "@radix-ui/react-dialog";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { SectionTitle } from "../../components/SectionTitle";
import { AdminError, fetchAdminJob, startAdminJob, type AdminJobInfo, type AdminOverview } from "../../lib/api";
import { cooldownText, phaseOf, PHASE_LABEL, type AdminJob, type Phase } from "../../lib/adminLogic";
import { formatAgo, formatDateTime } from "../../lib/format";
import type { Tone } from "../../lib/score";
import { useNow } from "./useAdminData";

type JobText = { title: string; button: string; text: string; confirm?: string };

const JOB_TEXT: Record<string, JobText> = {
  review: {
    title: "Prüfung jetzt ausführen",
    button: "Prüfung starten",
    text: "Wertet fällige Signale aus und erneuert Bilanz und Prüfbericht. Verändert weder Scores noch Eichung.",
  },
  maintain: {
    title: "Eichung neu erzeugen",
    button: "Eichung neu erzeugen",
    text: "Ergänzt fehlende Stichtage, erzeugt die Eichung und den Drift-Bericht neu. Kann einige Minuten dauern.",
  },
  score: {
    title: "Scores neu berechnen",
    button: "Scores berechnen",
    text: "Berechnet die Scores für heute neu und überschreibt die heutigen Werte.",
    confirm: "Die heutigen Scores werden neu berechnet und überschrieben. Fortfahren?",
  },
  evaluate: {
    title: "Signale auswerten",
    button: "Signale auswerten",
    text: "Vergleicht Signale, deren Zeitraum abgelaufen ist, mit dem tatsächlichen Kurs.",
  },
};
const ORDER = ["review", "maintain", "evaluate", "score"];

const PHASE_TONE: Record<Phase, Tone | null> = { idle: null, queued: "flat", running: "flat", done: "bull", failed: "bear" };

function Steps({ phase }: { phase: Phase }) {
  const active = phase === "queued" || phase === "running";
  if (!active) return null;
  return (
    <div role="status" className="mt-3">
      <p className="text-footnote font-medium text-ink">
        {phase === "queued" ? "Wartet auf den Start (wenige Sekunden bis Minuten) …" : "Läuft – bitte warten …"}
      </p>
      <div aria-hidden="true" className="mt-2 h-1.5 overflow-hidden rounded-chip bg-fill">
        <div className={`h-full rounded-chip bg-accent-solid motion-safe:animate-pulse ${phase === "queued" ? "w-1/3" : "w-2/3"}`} />
      </div>
    </div>
  );
}

function LogView({ id }: { id: number }) {
  const [log, setLog] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && log === null) {
      try {
        const job = await fetchAdminJob(id);
        setLog(job.log_tail?.trim() || "(kein Logauszug)");
      } catch (e) {
        setError((e as Error).message);
      }
    }
  };
  return (
    <div className="mt-2">
      <button type="button" aria-expanded={open} onClick={() => void toggle()} className="min-h-touch text-footnote font-semibold text-accent-ink underline underline-offset-2">
        {open ? "Logauszug ausblenden" : "Logauszug anzeigen"}
      </button>
      {open && (
        <pre tabIndex={0} aria-label="Logauszug" className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-control bg-fill p-3 text-caption text-ink">
          {error ?? log ?? "Lädt …"}
        </pre>
      )}
    </div>
  );
}

function Result({ job }: { job: AdminJob }) {
  const when = job.finished_at ?? job.requested_at;
  return (
    <div className="mt-3 border-t border-line pt-3">
      <p className="text-footnote text-ink-2">
        Letzter Auftrag: <time dateTime={when}>{formatDateTime(when)}</time> ({formatAgo(when)}){job.requested_by ? `, von ${job.requested_by}` : ""}
      </p>
      {job.summary && <p className={`mt-1 text-footnote ${job.status === "error" ? "font-medium text-bear-ink" : "text-ink"}`}>{job.summary}</p>}
      {(job.status === "ok" || job.status === "error") && <LogView id={job.id} />}
    </div>
  );
}

function JobCard({ info, jobs, onStart, busy, now, loadedAt }: { info: AdminJobInfo; jobs: AdminJob[]; onStart: (job: string) => void; busy: boolean; now: number; loadedAt: number }) {
  const text = JOB_TEXT[info.job] ?? JOB_TEXT.review!;
  const { phase, latest } = phaseOf(jobs, info.job);
  const active = info.active_id !== null || phase === "queued" || phase === "running";
  const wait = Math.max(0, info.wait_seconds - Math.max(0, now - loadedAt) / 1000);
  const waitText = cooldownText(wait);
  const tone = PHASE_TONE[phase];
  const disabled = active || busy || waitText !== null;
  return (
    <Card className="flex flex-col p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-body font-semibold tracking-tight">{text.title}</h3>
        {tone && <Badge tone={tone}>{PHASE_LABEL[phase]}</Badge>}
      </div>
      <p className="mt-1 text-footnote text-ink-2">{text.text}</p>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onStart(info.job)}
        className="mt-3 h-touch rounded-control bg-accent-solid px-4 text-subhead font-semibold text-on-accent disabled:bg-fill disabled:text-ink-2"
      >
        {active ? "Läuft bereits" : text.button}
      </button>
      <p className="mt-2 text-caption text-ink-2">
        {waitText ? `Wieder möglich ${waitText}` : `Abkühlzeit: ${info.cooldown_minutes} Min. nach jedem Lauf`}
      </p>
      <Steps phase={phase} />
      {latest && !active && <Result job={latest} />}
    </Card>
  );
}

function Confirm({ text, onCancel, onConfirm }: { text: string; onCancel: () => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open onOpenChange={(open) => !open && onCancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-scrim" />
        <Dialog.Content className="glass fixed left-1/2 top-1/2 z-50 w-[min(92vw,26rem)] -translate-x-1/2 -translate-y-1/2 rounded-card p-5 shadow-card ring-1 ring-edge">
          <Dialog.Title className="text-title3 font-bold tracking-title">Scores neu berechnen?</Dialog.Title>
          <Dialog.Description className="mt-2 text-subhead text-ink-2">{text}</Dialog.Description>
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={onCancel} className="h-touch rounded-control bg-fill px-4 text-subhead font-semibold text-ink hover:bg-fill-strong">
              Abbrechen
            </button>
            <button type="button" onClick={onConfirm} className="h-touch rounded-control bg-accent-solid px-4 text-subhead font-semibold text-on-accent">
              Ja, neu berechnen
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function JobsSection({ overview, loadedAt, reload }: { overview: AdminOverview; loadedAt: number; reload: () => Promise<void> }) {
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const anyWait = overview.jobs.some((j) => j.wait_seconds > 0);
  const now = useNow(anyWait);

  const start = async (job: string) => {
    setConfirm(null);
    setBusy(true);
    setMessage(null);
    try {
      await startAdminJob(job);
      setMessage({ text: `${JOB_TEXT[job]?.title ?? job}: eingereiht. Der Fortschritt erscheint hier.`, error: false });
    } catch (error) {
      setMessage({ text: (error as AdminError).message, error: true });
    } finally {
      setBusy(false);
      await reload();
    }
  };
  const request = (job: string) => (JOB_TEXT[job]?.confirm ? setConfirm(job) : void start(job));
  const infos = ORDER.map((job) => overview.jobs.find((j) => j.job === job)).filter((j): j is AdminJobInfo => !!j && j.job in JOB_TEXT);

  return (
    <section aria-labelledby="auftraege-title">
      <SectionTitle title="Prüfung auslösen" id="auftraege-title" />
      <p className="mb-3 text-subhead text-ink-2">
        Diese Läufe rechnet der Server. Danach kannst du den Bericht unten an Claude übergeben – Claude selbst wird von hier aus nie gestartet.
      </p>
      <div aria-live="polite" className="min-h-0">
        {message && (
          <p role={message.error ? "alert" : "status"} className={`mb-3 rounded-control px-3 py-2 text-footnote ${message.error ? "bg-bear-soft text-bear-ink" : "bg-fill text-ink"}`}>
            {message.text}
          </p>
        )}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {infos.map((info) => (
          <JobCard key={info.job} info={info} jobs={overview.recent_jobs} onStart={request} busy={busy} now={now} loadedAt={loadedAt} />
        ))}
      </div>
      {confirm && <Confirm text={JOB_TEXT[confirm]?.confirm ?? ""} onCancel={() => setConfirm(null)} onConfirm={() => void start(confirm)} />}
    </section>
  );
}
