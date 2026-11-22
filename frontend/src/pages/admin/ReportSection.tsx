import { useState } from "react";

import { Card } from "../../components/Card";
import { ErrorState } from "../../components/ErrorState";
import { NoData } from "../../components/ErrorState";
import { SectionTitle } from "../../components/SectionTitle";
import { Skeleton } from "../../components/Skeleton";
import { Table, Td, Th } from "../../components/Table";
import { fetchAdminReport, type AdminReport } from "../../lib/api";
import { buildClaudePrompt, driftNumber, driftText, groupsOf } from "../../lib/adminLogic";
import { formatDate, formatDateTime, formatPct } from "../../lib/format";
import { useApi } from "../../lib/useApi";
import { DRIFT_SHORT } from "../../lib/trackrecord";
import { CLASS_LABEL } from "../overview/model";

const PROFILE: Record<string, string> = { swing: "Swing", long_term: "Langfristig" };
const share = (v: number | null) => (v === null ? "–" : formatPct(v * 100, 1));
const edge = (v: number | null) => (v === null ? "–" : formatPct(v * 100, 2));

/** Zwischenablage: moderne API, sonst Auswahl in einem versteckten Textfeld (z. B. ohne HTTPS). */
async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    try {
      return document.execCommand("copy");
    } finally {
      area.remove();
    }
  }
}

function Actions({ report }: { report: AdminReport }) {
  const [copied, setCopied] = useState<"idle" | "ok" | "fail">("idle");
  const stand = driftText(report.drift, "today");
  const copy = async () => {
    const ok = await copyText(buildClaudePrompt(report.review_md, stand));
    setCopied(ok ? "ok" : "fail");
    window.setTimeout(() => setCopied("idle"), 4000);
  };
  const button = "inline-flex h-touch items-center justify-center rounded-control px-4 text-subhead font-semibold";
  return (
    <div className="mt-4">
      <div className="flex flex-col gap-2 sm:flex-row">
        <button type="button" onClick={() => void copy()} className={`${button} bg-accent-solid text-on-accent`}>
          Für Claude kopieren
        </button>
        {report.review_md ? (
          <a href="/api/admin/report.md" download={report.filename} className={`${button} bg-fill text-ink hover:bg-fill-strong`}>
            Download .md
          </a>
        ) : (
          <span aria-disabled="true" className={`${button} bg-fill text-ink-2`}>
            Download .md
          </span>
        )}
      </div>
      <p role="status" className="mt-2 min-h-5 text-footnote text-ink-2">
        {copied === "ok" && "Kopiert. In Claude Code einfügen (Strg/⌘ V)."}
        {copied === "fail" && "Kopieren nicht möglich: bitte den Download verwenden."}
      </p>
    </div>
  );
}

export function ReportSection({ refreshKey }: { refreshKey: number }) {
  const { state, reload } = useApi((signal) => fetchAdminReport(signal), [refreshKey]);
  return (
    <section aria-labelledby="bericht-title">
      <SectionTitle title="Prüfbericht" id="bericht-title" />
      {state.status === "loading" && <Skeleton className="h-48 w-full" />}
      {state.status === "error" && <ErrorState what="Der Prüfbericht" onRetry={reload} />}
      {state.status === "ready" && <ReportBody report={state.data} />}
    </section>
  );
}

function ReportBody({ report }: { report: AdminReport }) {
  const groups = groupsOf(report.drift);
  const stand = driftText(report.drift, "today");
  const evaluated = driftNumber(report.drift, "evaluated");
  const open = driftNumber(report.drift, "open");
  const since = driftText(report.drift, "live_since");
  const model = driftText(report.drift, "model_version");
  return (
    <Card className="p-4 sm:p-5">
      {!report.review_md && !report.drift ? (
        <NoData title="Noch kein Prüfbericht" text="Starte oben „Prüfung jetzt ausführen“. Danach erscheint hier die aktuelle Bilanz." />
      ) : (
        <>
          <p className="text-subhead text-ink-2">
            Datenstand {stand ? formatDate(stand) : "–"}
            {model ? `, Modell ${model}` : ""}
            {since ? `. Live seit ${formatDate(since)}` : ""}
            {evaluated !== null ? `, ${evaluated} ausgewertete Signale` : ""}
            {open !== null ? `, ${open} offen` : ""}.
            {report.review_updated_at ? ` Bericht erstellt ${formatDateTime(report.review_updated_at)}.` : ""}
          </p>
          {groups.length > 0 && (
            <div className="mt-3">
              <Table caption="Bilanz je Profil und Klasse (wöchentliche Signale)">
                <thead>
                  <tr>
                    <Th>Profil</Th>
                    <Th>Klasse</Th>
                    <Th right>n / n_eff</Th>
                    <Th right>Wochen</Th>
                    <Th right>Treffer (Basis)</Th>
                    <Th right>Vorteil live</Th>
                    <Th right>Vorteil Eichung</Th>
                    <Th>Status</Th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr key={`${g.profile}-${g.asset_class}`}>
                      <Td strong>{PROFILE[g.profile] ?? g.profile}</Td>
                      <Td>{CLASS_LABEL[g.asset_class as keyof typeof CLASS_LABEL] ?? g.asset_class}</Td>
                      <Td right>
                        {g.n} / {g.n_eff}
                      </Td>
                      <Td right>{g.weeks}</Td>
                      <Td right>
                        {share(g.hit)} ({share(g.base_hit)})
                      </Td>
                      <Td right>{edge(g.edge)}</Td>
                      <Td right>{edge(g.cal_edge)}</Td>
                      <Td>{DRIFT_SHORT[g.status as keyof typeof DRIFT_SHORT] ?? g.status}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
          <Actions report={report} />
          {report.review_md && (
            <details className="mt-3">
              <summary className="flex min-h-touch cursor-pointer items-center text-footnote font-semibold text-accent-ink">Bericht als Text (Markdown) ansehen</summary>
              <pre tabIndex={0} aria-label="Prüfbericht als Markdown" className="mt-1 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-control bg-fill p-3 text-caption text-ink">
                {report.review_md}
              </pre>
            </details>
          )}
          <p className="mt-3 text-caption text-ink-2">Der Bericht misst und meldet. Er enthält keine Empfehlung und ändert nichts am Modell.</p>
        </>
      )}
    </Card>
  );
}
