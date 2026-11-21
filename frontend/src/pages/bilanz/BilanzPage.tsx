import { Card } from "../../components/Card";
import { DriftBadge } from "../../components/DriftBadge";
import { TimeChart, type SeriesSpec } from "../../components/charts/TimeChart";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { IconBilanz } from "../../components/icons";
import { InfoTip } from "../../components/InfoTip";
import { PageHeader } from "../../components/PageHeader";
import { SectionTitle } from "../../components/SectionTitle";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Skeleton } from "../../components/Skeleton";
import { useUi } from "../../components/ui-context";
import { fetchTrackrecord, type AssetClass, type FactorDrift, type ProfileKey, type TrackGroup, type Trackrecord } from "../../lib/api";
import { formatDate, formatDecimal } from "../../lib/format";
import { factorLabel } from "../../lib/glossary";
import { usePersistentState } from "../../lib/usePersistentState";
import { useApi } from "../../lib/useApi";
import { FACTOR_STATUS_LABEL, factorWarning, formatEdge, formatShare, headerText, missingText, progressPct } from "../../lib/trackrecord";
import { CLASS_LABEL } from "../overview/model";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];
const PROFILE_OPTIONS = [
  { value: "swing" as const, label: "Swing" },
  { value: "long_term" as const, label: "Langfristig" },
];
const SERIES_COLORS = ["--c-series-1", "--c-series-2", "--c-series-3", "--c-series-4"];

function Head({ data }: { data: Trackrecord }) {
  const { explain } = useUi();
  return (
    <Card className="p-4 sm:p-6">
      <p className="text-body font-semibold">{headerText(data)}</p>
      <p className="mt-2 text-subhead text-ink-2">
        Die Bilanz prüft die Zukunft: Jedes Signal von heute wird nach Ablauf seines Zeitraums mit dem tatsächlichen Kurs verglichen. Das ist keine Prognose und keine Anlageberatung.
      </p>
      <button type="button" onClick={() => explain("trackrecord")} className="mt-1 inline-flex min-h-touch items-center text-footnote font-semibold text-accent-ink underline underline-offset-2">
        Wie lese ich das?
      </button>
    </Card>
  );
}

function Progress({ data }: { data: Trackrecord }) {
  const pct = progressPct(data.progress);
  return (
    <section aria-labelledby="fortschritt-title">
      <SectionTitle title="Fortschritt der Eichung" term="calibratedProgress" id="fortschritt-title" />
      <Card className="p-4 sm:p-6">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-body font-semibold">Eichung zu {pct} % belegt</p>
          <p className="num text-footnote text-ink-2">
            {data.calibrated_groups} von {data.groups.length} Gruppen geeicht
          </p>
        </div>
        <div role="progressbar" aria-label="Eichung belegt" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} className="mt-2 h-2.5 overflow-hidden rounded-chip bg-fill">
          <div className="h-full rounded-chip bg-accent-solid motion-safe:transition-[width] motion-safe:duration-500" style={{ width: `${Math.max(pct, pct > 0 ? 2 : 0)}%` }} />
        </div>
        <ul className="mt-3 flex flex-col gap-1 text-footnote text-ink-2">
          {data.groups.map((g) => (
            <li key={`${g.profile}-${g.asset_class}`} className="flex flex-wrap justify-between gap-x-3">
              <span className="font-medium text-ink">{CLASS_LABEL[g.asset_class]}</span>
              <span>{g.calibrated ? "geeicht" : missingText(data, g) || "Live-Vorteil noch nicht im Rahmen der Eichung"}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-footnote text-ink-2">
          Kriterien je Gruppe: mindestens {data.criteria.min_n_eff} unabhängige Fälle, {data.criteria.min_months} Monate und {data.criteria.min_weeks} Wochen Live-Betrieb, Live-Vorteil im Rahmen der Eichung oder besser.
          {data.done_from && <> Frühester Zeitpunkt: {formatDate(data.done_from)}.</>} „Geeicht“ heißt „Aussage belastbar geprüft“, nicht „profitabel“.
        </p>
      </Card>
    </section>
  );
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-caption text-ink-2">{label}</dt>
      <dd className="num text-subhead font-semibold">{children}</dd>
    </div>
  );
}

const hitText = (g: TrackGroup) => (g.hit === null ? "–" : `${formatShare(g.hit)} (Basis ${formatShare(g.base_hit)})`);
const nText = (g: TrackGroup) => `${g.n} / ${formatDecimal(g.n_eff, 1)}`;

function GroupTable({ groups }: { groups: TrackGroup[] }) {
  return (
    <>
      <div className="hidden sm:block">
        <table className="w-full border-collapse text-subhead">
          <caption className="sr-only">Live-Bilanz je Profil und Assetklasse</caption>
          <thead>
            <tr className="text-caption text-ink-2">
              <th scope="col" className="py-2 pr-3 text-left font-medium">Klasse</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Status</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Trefferquote (Basis)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Vorteil live</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Vorteil Eichung</th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">n / n_eff · Wochen</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.asset_class} className="border-t border-line">
                <th scope="row" className="py-2.5 pr-3 text-left font-semibold">{CLASS_LABEL[g.asset_class]}</th>
                <td className="px-3 py-2.5"><DriftBadge status={g.status} /></td>
                <td className="num px-3 py-2.5 text-right">{hitText(g)}</td>
                <td className="num px-3 py-2.5 text-right">{formatEdge(g.edge)}</td>
                <td className="num px-3 py-2.5 text-right text-ink-2">{formatEdge(g.cal_edge)}</td>
                <td className="num py-2.5 pl-3 text-right">{nText(g)} · {g.weeks}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-col gap-3 sm:hidden">
        {groups.map((g) => (
          <li key={g.asset_class} className="rounded-control bg-fill p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-body font-semibold">{CLASS_LABEL[g.asset_class]}</h3>
              <DriftBadge status={g.status} />
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2">
              <Metric label="Trefferquote (Basis)">{hitText(g)}</Metric>
              <Metric label="Vorteil live">{formatEdge(g.edge)}</Metric>
              <Metric label="Vorteil Eichung">{formatEdge(g.cal_edge)}</Metric>
              <Metric label="n / n_eff · Wochen">{nText(g)} · {g.weeks}</Metric>
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}

function Groups({ data, profile }: { data: Trackrecord; profile: ProfileKey }) {
  const groups = data.groups.filter((g) => g.profile === profile);
  const empty = data.evaluated === 0;
  return (
    <section aria-labelledby="gruppen-title">
      <SectionTitle title="Bilanz je Klasse" term="driftStatus" id="gruppen-title" />
      <Card className="p-4 sm:p-6">
        {empty && (
          <p role="note" className="mb-4 rounded-control bg-flat-soft px-3.5 py-2.5 text-footnote font-semibold text-ink ring-1 ring-flat-ring/40">
            Noch keine ausgewerteten Signale: {data.open} laufen noch.
            {data.earliest_due ? ` Das erste Ende eines Zeitraums liegt voraussichtlich um den ${formatDate(data.earliest_due)}.` : ""} Bis dahin steht überall „zu früh“; das ist ein Ergebnis, kein Fehler.
          </p>
        )}
        {!empty && groups.every((g) => g.status === "zu_frueh") && (
          <p className="mb-4 text-footnote text-ink-2">
            Zu früh für eine Aussage: Es fehlen noch unabhängige Fälle (mindestens {data.criteria.min_n_eff_status}) oder Wochen (mindestens {data.criteria.min_weeks_status}). Signale derselben Woche sind nicht unabhängig.
          </p>
        )}
        <GroupTable groups={groups} />
        <p className="mt-3 text-footnote text-ink-2">
          Nur wöchentliche Signale (freitags), Zeitraum je Profil: {groups[0]?.horizon ?? "–"} Handelstage. Vorteil = Ø Rendite in Signalrichtung minus Ø aller Fälle, in Prozentpunkten (PP). Modellstand {data.model_version}.
        </p>
      </Card>
    </section>
  );
}

function sameFactor(f: FactorDrift) {
  return `${f.asset_class}-${f.factor}`;
}

function Factors({ data, profile }: { data: Trackrecord; profile: ProfileKey }) {
  const factors = data.factors.filter((f) => f.profile === profile);
  const warnings = factors.filter((f) => f.warn);
  return (
    <section aria-labelledby="faktoren-title">
      <SectionTitle title="Faktor-Drift" term="factorDrift" id="faktoren-title" />
      <Card className="p-4 sm:p-6">
        {warnings.length > 0 ? (
          <div role="note" className="mb-3 rounded-control bg-flat-soft px-3.5 py-2.5 ring-1 ring-flat-ring/40">
            <ul className="flex flex-col gap-1 text-footnote font-semibold">
              {warnings.map((f) => (
                <li key={sameFactor(f)}>{factorWarning(f, factorLabel(f.factor), CLASS_LABEL[f.asset_class])}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mb-3 text-subhead">Keine Warnung. Faktoren, die live gegenläufig laufen, erscheinen hier; geändert wird nichts automatisch.</p>
        )}
        {factors.length === 0 ? (
          <p className="text-footnote text-ink-2">Noch keine Faktor-Auswertung: Dafür braucht es ausgewertete Signale.</p>
        ) : (
          <ul className="divide-y divide-line">
            {factors.map((f) => (
              <li key={sameFactor(f)} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-2 text-footnote">
                <span className="font-medium text-ink">
                  {factorLabel(f.factor)} <span className="font-normal text-ink-2">({CLASS_LABEL[f.asset_class]})</span>
                </span>
                <span className="num text-ink-2">
                  IC live {f.ic === null ? "–" : formatDecimal(f.ic, 2)} · Backtest {f.backtest_ic === null ? "–" : formatDecimal(f.backtest_ic, 2)} · {FACTOR_STATUS_LABEL[f.status]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function Course({ data, profile }: { data: Trackrecord; profile: ProfileKey }) {
  const bundle = data.series[profile] ?? {};
  const classes = Object.keys(bundle) as AssetClass[];
  const weeks = Math.max(0, ...classes.map((k) => bundle[k]?.length ?? 0));
  const enough = weeks >= data.criteria.min_weeks_status && weeks >= 2;
  const series: SeriesSpec[] = classes.map((k, i) => ({
    id: k,
    name: CLASS_LABEL[k],
    data: (bundle[k] ?? []).map((p) => [p.date, p.value] as [string, number]),
    color: SERIES_COLORS[i % SERIES_COLORS.length] ?? "--c-series-1",
    step: true,
    format: (v: number) => formatDecimal(v, 1),
  }));
  return (
    <section aria-labelledby="verlauf-title">
      <SectionTitle title="Zeitverlauf" id="verlauf-title" />
      <Card className="p-4 sm:p-6">
        {enough ? (
          <>
            <TimeChart series={series} height={220} label="Kumulierte Treffer-Differenz der wöchentlichen Signale je Klasse" guide={{ value: 0, title: "Zufall (Basis)" }} />
            <p className="mt-3 text-footnote text-ink-2">
              Kumulierte Treffer-Differenz: Treffer minus die nach der Basisrate erwarteten Treffer, je Klasse über die Zeit. Steigend heißt mehr Treffer als nach der Basis zu erwarten wären; um null liegt der Zufall.
            </p>
          </>
        ) : (
          <p className="text-subhead text-ink-2">Der Zeitverlauf erscheint, sobald mindestens {Math.max(2, data.criteria.min_weeks_status)} Wochen mit ausgewerteten Signalen vorliegen. Aktuell: {weeks}.</p>
        )}
      </Card>
    </section>
  );
}

function Skeletons() {
  return (
    <div aria-busy="true" aria-label="Lädt" className="flex flex-col gap-6 px-4 sm:px-8">
      <Skeleton className="h-32 w-full rounded-card" />
      <Skeleton className="h-72 w-full rounded-card" />
      <Skeleton className="h-48 w-full rounded-card" />
    </div>
  );
}

export function BilanzPage() {
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const { state, reload } = useApi((signal) => fetchTrackrecord(profile, signal), [profile]);
  return (
    <>
      <PageHeader title="Bilanz" subtitle="Stimmen die Signale mit dem realen Kurs überein?" />
      {state.status === "loading" && <Skeletons />}
      {state.status === "error" && (
        <div className="px-4 sm:px-8">
          <ErrorState what="Die Bilanz" onRetry={reload} />
        </div>
      )}
      {state.status === "ready" && (
        <div className="flex flex-col gap-6 px-4 sm:px-8">
          <Head data={state.data} />
          <SegmentedControl label="Profil" value={profile} onChange={setProfile} options={PROFILE_OPTIONS} full className="sm:w-72" />
          {state.data.live_since === null ? (
            <Card>
              <EmptyState icon={<IconBilanz size={28} />} title="Noch keine Live-Signale" text="Sobald der Score-Lauf Signale erzeugt und deren Zeitraum abgelaufen ist, erscheint hier die Bilanz." />
            </Card>
          ) : (
            <>
              <Groups data={state.data} profile={profile} />
              <Progress data={state.data} />
              <Factors data={state.data} profile={profile} />
              <Course data={state.data} profile={profile} />
            </>
          )}
          <p className="text-footnote text-ink-2">
            Datenstand: Auswertung täglich, Eichung wöchentlich neu erzeugt{state.data.calibration_date ? ` (zuletzt ${formatDate(state.data.calibration_date)})` : ""}. <InfoTip term="calibration" />
          </p>
        </div>
      )}
    </>
  );
}
