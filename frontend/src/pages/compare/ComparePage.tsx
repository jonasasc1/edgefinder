import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { TimeChart, type SeriesSpec } from "../../components/charts/TimeChart";
import { Delta } from "../../components/Delta";
import { Button, EmptyState } from "../../components/EmptyState";
import { ErrorState, NoData } from "../../components/ErrorState";
import { IconClose, IconPlus, IconSearch } from "../../components/icons";
import { InfoTip } from "../../components/InfoTip";
import { PageHeader } from "../../components/PageHeader";
import { ScoreBar } from "../../components/ScoreBar";
import { ScoreRing } from "../../components/ScoreRing";
import { SectionTitle } from "../../components/SectionTitle";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Sheet } from "../../components/Sheet";
import { Skeleton } from "../../components/Skeleton";
import { fetchAssetDetail, fetchHistory, fetchProfiles, type AssetDetail, type History, type ProfileKey } from "../../lib/api";
import { useAssets } from "../../lib/assets";
import { MAX_COMPARE } from "../../lib/favorites";
import { formatDecimal, formatPct } from "../../lib/format";
import { factorLabel, FACTORS } from "../../lib/glossary";
import { levelOf, toneOf } from "../../lib/score";
import { RANGE_KEYS, RANGES, type RangeKey } from "../../lib/stats";
import { useApi } from "../../lib/useApi";
import { usePersistentState } from "../../lib/usePersistentState";
import { CLASS_LABEL } from "../overview/model";
import { factorRows, normalizedPrices, parseCompareIds } from "./model";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];
const SERIES_COLORS = ["--c-series-1", "--c-series-2", "--c-series-3", "--c-series-4"];
const SERIES_CLASS = ["bg-series-1", "bg-series-2", "bg-series-3", "bg-series-4"];

function Picker({ open, onOpenChange, taken, onPick }: { open: boolean; onOpenChange: (open: boolean) => void; taken: string[]; onPick: (id: string) => void }) {
  const { state } = useAssets(open);
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const items = state.status === "ready" ? state.assets.filter((a) => !taken.includes(a.id) && (!q || a.id.toLowerCase().includes(q) || a.name.toLowerCase().includes(q))) : [];
  return (
    <Sheet open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) setQuery(""); }} title="Asset hinzufügen" description={`Vergleiche bis zu ${MAX_COMPARE} Assets.`}>
      <label className="relative block">
        <span className="sr-only">Asset suchen</span>
        <IconSearch size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-2" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Name oder Kürzel"
          className="h-touch w-full rounded-control bg-fill pl-10 pr-3 text-body placeholder:text-ink-2"
        />
      </label>
      <ul className="mt-3 max-h-72 divide-y divide-line overflow-y-auto">
        {items.map((asset) => (
          <li key={asset.id}>
            <button type="button" onClick={() => { onPick(asset.id); onOpenChange(false); setQuery(""); }} className="flex min-h-touch w-full items-center justify-between gap-3 py-2 text-left">
              <span className="min-w-0">
                <span className="block font-semibold">{asset.id}</span>
                <span className="block truncate text-footnote text-ink-2">{asset.name}</span>
              </span>
              <span className="text-caption text-ink-2">{CLASS_LABEL[asset.asset_class]}</span>
            </button>
          </li>
        ))}
        {state.status === "ready" && items.length === 0 && <li className="py-6 text-center text-subhead text-ink-2">Kein Asset gefunden.</li>}
        {state.status === "loading" && <li className="py-6"><Skeleton className="h-10 w-full" /></li>}
      </ul>
    </Sheet>
  );
}

type Loaded = { details: AssetDetail[]; histories: History[] };

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const { state: assetsState, reload: reloadAssets } = useAssets();
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const [range, setRange] = usePersistentState<RangeKey>("ef-range", "1y", RANGE_KEYS);
  const profiles = useApi((signal) => fetchProfiles(signal), []);
  const [pickerOpen, setPickerOpen] = useState(false);

  const known = useMemo(() => (assetsState.status === "ready" ? assetsState.assets.map((a) => a.id) : []), [assetsState]);
  const ids = useMemo(() => parseCompareIds(params.get("ids"), known), [params, known]);
  const idsKey = ids.join(",");
  const setIds = (next: string[]) => setParams(next.length ? { ids: next.join(",") } : {}, { replace: true });

  const { state, reload } = useApi<Loaded>(
    (signal) => Promise.all([Promise.all(ids.map((id) => fetchAssetDetail(id, signal))), Promise.all(ids.map((id) => fetchHistory(id, 1830, signal)))]).then(([details, histories]) => ({ details, histories })),
    [idsKey],
  );

  const options = (profiles.state.status === "ready" ? profiles.state.data : [{ key: "swing" as const, label: "Swing" }, { key: "long_term" as const, label: "Langfristig" }]).map((p) => ({ value: p.key, label: p.label }));
  const days = RANGES.find((r) => r.value === range)?.days ?? 366;
  const loaded = state.status === "ready" && ids.length >= 2 ? state.data : null;

  const series = useMemo<SeriesSpec[]>(() => {
    if (!loaded) return [];
    const normalized = normalizedPrices(loaded.histories.map((h) => h.prices), days);
    return normalized.flatMap((data, index) => {
      const id = ids[index];
      const color = SERIES_COLORS[index];
      if (!id || !color || data.length === 0) return [];
      return [{ id, name: id, data, color, kind: "line" as const, format: (v: number) => formatDecimal(v, 1) }];
    });
  }, [loaded, days, ids]);

  const rows = loaded ? factorRows(loaded.details, profile) : [];
  const waiting = assetsState.status === "loading" || assetsState.status === "idle";

  return (
    <>
      <PageHeader title="Vergleich" subtitle="Scores, Teilscores und Kurse nebeneinander" />
      <div className="flex flex-col gap-6 px-4 sm:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <SegmentedControl label="Profil" value={profile} onChange={setProfile} options={options} full className="sm:w-72" />
          <ul className="flex flex-wrap items-center gap-2" aria-label="Ausgewählte Assets">
            {ids.map((id, index) => (
              <li key={id} className="flex h-touch items-center gap-2 rounded-chip bg-surface pl-3.5 pr-1 shadow-card ring-1 ring-edge">
                <span aria-hidden="true" className={`size-2.5 rounded-chip ${SERIES_CLASS[index]}`} />
                <span className="text-subhead font-semibold">{id}</span>
                <button type="button" onClick={() => setIds(ids.filter((x) => x !== id))} aria-label={`${id} entfernen`} className="grid size-9 place-items-center rounded-chip text-ink-2">
                  <IconClose size={16} />
                </button>
              </li>
            ))}
            {ids.length < MAX_COMPARE && (
              <li>
                <button type="button" onClick={() => setPickerOpen(true)} className="flex h-touch items-center gap-1.5 rounded-chip bg-fill px-4 text-subhead font-semibold">
                  <IconPlus size={18} />
                  Asset hinzufügen
                </button>
              </li>
            )}
          </ul>
        </div>

        {assetsState.status === "error" && <ErrorState what="Die Assets" onRetry={reloadAssets} />}

        {!waiting && assetsState.status !== "error" && ids.length < 2 && (
          <Card>
            <EmptyState
              art="empty"
              title={ids.length === 0 ? "Wähle Assets zum Vergleichen" : "Wähle ein zweites Asset"}
              text="Du kannst zwei bis vier Assets nebeneinanderstellen, zum Beispiel EURUSD und GOLD. Auch über die Suche (Strg+K) geht das schnell."
              action={<Button onClick={() => setPickerOpen(true)}>Asset hinzufügen</Button>}
            />
          </Card>
        )}

        {ids.length >= 2 && state.status === "loading" && (
          <div aria-busy="true" aria-label="Lädt" className="flex flex-col gap-6">
            <Skeleton className="h-60 w-full rounded-card" />
            <Skeleton className="h-80 w-full rounded-card" />
          </div>
        )}
        {ids.length >= 2 && state.status === "error" && <ErrorState what="Der Vergleich" onRetry={reload} />}

        {loaded && (
          <>
            <ul className={`grid grid-cols-2 gap-3 sm:gap-4 ${loaded.details.length === 2 ? "" : loaded.details.length === 3 ? "lg:grid-cols-3" : "lg:grid-cols-4"}`}>
              {loaded.details.map((detail, index) => {
                const entry = detail.profiles[profile]?.score;
                return (
                  <li key={detail.id}>
                    <Card className="h-full">
                      <Link to={`/asset/${detail.id}`} className="flex h-full flex-col items-center gap-2.5 rounded-card p-4 text-center sm:p-5">
                        <div className="flex w-full items-center justify-between gap-2">
                          <span className="flex items-center gap-2 text-body font-bold tracking-tight"><span aria-hidden="true" className={`size-2.5 rounded-chip ${SERIES_CLASS[index]}`} />{detail.id}</span>
                          <span className="text-caption text-ink-2">{CLASS_LABEL[detail.asset_class]}</span>
                        </div>
                        <div className="line-clamp-2 min-h-10 w-full text-left text-footnote text-ink-2">{detail.name}</div>
                        <ScoreRing score={entry?.score ?? null} label={entry?.label} size="md" />
                        {entry ? <Badge tone={toneOf(levelOf(entry.score, entry.label))}>{entry.label}</Badge> : <Badge tone="flat">Keine Daten</Badge>}
                      </Link>
                    </Card>
                  </li>
                );
              })}
            </ul>

            <section aria-labelledby="cmp-factors">
              <SectionTitle id="cmp-factors" title="Teilscores" term="score" />
              <Card variant="group">
                <div tabIndex={0} role="region" aria-label="Teilscores, waagerecht scrollbar" className="scroll-hidden relative overflow-x-auto">
                  <table className="w-full min-w-max border-collapse">
                    <caption className="sr-only">Teilscores der verglichenen Assets</caption>
                    <thead>
                      <tr>
                        <th scope="col" className="sticky left-0 z-10 bg-surface px-4 py-3 text-left text-footnote font-medium text-ink-2 sm:px-5">Faktor</th>
                        {loaded.details.map((detail) => (
                          <th key={detail.id} scope="col" className="min-w-28 px-3 py-3 text-left text-footnote font-semibold">{detail.id}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((factor) => (
                        <tr key={factor} className="border-t border-line">
                          <th scope="row" className="sticky left-0 z-10 whitespace-nowrap bg-surface px-4 py-3 text-left text-footnote font-medium sm:px-5">
                            <span className="flex items-center gap-1">{factorLabel(factor)}{FACTORS[factor]?.term && <InfoTip term={FACTORS[factor].term} />}</span>
                          </th>
                          {loaded.details.map((detail) => {
                            const component = detail.profiles[profile]?.components.find((c) => c.factor === factor);
                            const value = component?.subscore ?? null;
                            return (
                              <td key={detail.id} className="px-3 py-3 align-middle">
                                {component === undefined || value === null ? (
                                  <span className="text-footnote text-ink-2">–<span className="sr-only"> keine Daten</span></span>
                                ) : (
                                  <div className="w-24">
                                    <ScoreBar value={value} />
                                    <div className="num mt-1 text-footnote font-medium">{formatDecimal(value, 2)}</div>
                                  </div>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                      <tr className="border-t border-line">
                        <th scope="row" className="sticky left-0 z-10 bg-surface px-4 py-3 text-left text-footnote font-medium sm:px-5">
                          <span className="flex items-center gap-1">Abdeckung <InfoTip term="coverage" /></span>
                        </th>
                        {loaded.details.map((detail) => {
                          const entry = detail.profiles[profile]?.score;
                          return <td key={detail.id} className="num px-3 py-3 text-footnote font-medium">{entry ? formatPct(entry.coverage * 100, 0) : "–"}</td>;
                        })}
                      </tr>
                      <tr className="border-t border-line">
                        <th scope="row" className="sticky left-0 z-10 bg-surface px-4 py-3 text-left text-footnote font-medium sm:px-5">Seit gestern</th>
                        {loaded.details.map((detail) => <td key={detail.id} className="px-3 py-3 text-footnote"><Delta value={detail.profiles[profile]?.score.change_1d} /></td>)}
                      </tr>
                      <tr className="border-t border-line">
                        <th scope="row" className="sticky left-0 z-10 bg-surface px-4 py-3 text-left text-footnote font-medium sm:px-5">Seit einer Woche</th>
                        {loaded.details.map((detail) => <td key={detail.id} className="px-3 py-3 text-footnote"><Delta value={detail.profiles[profile]?.score.change_7d} /></td>)}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>

            <section aria-labelledby="cmp-chart">
              <SectionTitle
                id="cmp-chart"
                title="Kursverlauf, normiert"
                aside={<SegmentedControl label="Zeitraum" size="sm" value={range} onChange={setRange} options={RANGES.map((r) => ({ value: r.value, label: r.label }))} />}
              />
              <Card className="p-4 sm:p-5">
                {series.length === 0 ? (
                  <NoData text="Für diesen Zeitraum liegen keine Kurse vor. Wähle einen längeren Zeitraum." />
                ) : (
                  <>
                    <TimeChart series={series} height={300} guide={{ value: 100, title: "" }} label={`Normierter Kursverlauf von ${ids.join(", ")}`} />
                    <p className="mt-3 text-footnote text-ink-2">Alle Kurse starten am gleichen Tag bei 100, so siehst du die relative Entwicklung unabhängig vom Preisniveau.</p>
                  </>
                )}
              </Card>
            </section>
          </>
        )}
      </div>
      <Picker open={pickerOpen} onOpenChange={setPickerOpen} taken={ids} onPick={(id) => setIds([...ids, id])} />
    </>
  );
}
