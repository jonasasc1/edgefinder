import { useMemo, useState } from "react";

import { Card } from "../../components/Card";
import { ErrorState, NoData } from "../../components/ErrorState";
import { InfoTip } from "../../components/InfoTip";
import { PageHeader } from "../../components/PageHeader";
import { ScoreBar } from "../../components/ScoreBar";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Sheet } from "../../components/Sheet";
import { Skeleton } from "../../components/Skeleton";
import { Tooltip } from "../../components/Tooltip";
import { fetchMacro, fetchProfiles, type MacroEconomy, type MacroIndicator, type ProfileKey } from "../../lib/api";
import { formatDateMedium, formatDecimal, formatDelta } from "../../lib/format";
import { CATEGORY_LABEL } from "../../lib/glossary";
import { useApi } from "../../lib/useApi";
import { usePersistentState } from "../../lib/usePersistentState";
import { heatColumns, heatShare, indicatorOf, type Column } from "./model";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];
type Selected = { economy: MacroEconomy; indicator: MacroIndicator };

function cellStyle(indicator: MacroIndicator) {
  if (!indicator.fresh) return undefined;
  const { tone, share } = heatShare(indicator.score);
  if (tone === "flat") return undefined;
  return { backgroundColor: `color-mix(in srgb, var(--c-${tone}-ring) ${share}%, transparent)` };
}

const verdict = (score: number | null) => (score === null ? "ohne Wertung" : score > 0.02 ? "besser als üblich" : score < -0.02 ? "schlechter als üblich" : "unauffällig");

function Cell({ economy, column, onSelect }: { economy: MacroEconomy; column: Column; onSelect: (selected: Selected) => void }) {
  const indicator = indicatorOf(economy, column.key);
  if (!indicator) {
    return (
      <td className="border-t border-line p-0.5">
        <div className="grid h-touch min-w-20 place-items-center text-footnote text-ink-2" aria-label="wird nicht erfasst">–</div>
      </td>
    );
  }
  const text = indicator.value === null ? "–" : formatDecimal(indicator.value, 1);
  return (
    <td className="border-t border-line p-0.5">
      <Tooltip
        content={
          <span className="block">
            <strong className="block">{indicator.label}</strong>
            <span className="num block">
              {text}
              {indicator.date && ` · Stand ${formatDateMedium(indicator.date)}`}
            </span>
            <span className="block text-ink-2">{indicator.fresh ? verdict(indicator.score) : "Daten zu alt für den Score"}</span>
          </span>
        }
      >
        <button
          type="button"
          onClick={() => onSelect({ economy, indicator })}
          aria-label={`${economy.name}, ${indicator.label}: ${text}, ${indicator.fresh ? verdict(indicator.score) : "veraltet"}`}
          style={cellStyle(indicator)}
          className={`num grid h-touch w-full min-w-20 place-items-center rounded-thumb text-footnote font-semibold ${
            indicator.value === null || !indicator.fresh ? "bg-fill text-ink-2" : indicator.score === null || heatShare(indicator.score).tone === "flat" ? "bg-fill text-ink" : "text-ink"
          }`}
        >
          {text}
        </button>
      </Tooltip>
    </td>
  );
}

function Heatmap({ economies, columns, onSelect }: { economies: MacroEconomy[]; columns: Column[]; onSelect: (selected: Selected) => void }) {
  const groups = columns.reduce<{ category: string; span: number }[]>((acc, column) => {
    const last = acc[acc.length - 1];
    if (last?.category === column.category) last.span += 1;
    else acc.push({ category: column.category, span: 1 });
    return acc;
  }, []);
  return (
    <div className="scroll-hidden relative overflow-x-auto" tabIndex={0} role="region" aria-label="Heatmap der Wirtschaftsdaten, waagerecht scrollbar">
      <table className="w-full border-separate border-spacing-0">
        <caption className="sr-only">Wirtschaftsdaten je Land und Indikator</caption>
        <thead>
          <tr>
            <td className="sticky left-0 z-10 bg-surface" />
            {groups.map((group, index) => (
              <th key={group.category} colSpan={group.span} scope="colgroup" className={`px-1 pb-1 pt-3 text-left text-footnote font-semibold text-ink ${index > 0 ? "border-l border-line pl-2" : ""}`}>
                {CATEGORY_LABEL[group.category] ?? group.category}
              </th>
            ))}
          </tr>
          <tr>
            <th scope="col" className="sticky left-0 z-10 bg-surface px-3 pb-2 text-left text-footnote font-medium text-ink-2">Land</th>
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-1 pb-2 text-center text-caption font-medium text-ink-2">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {economies.map((economy) => (
            <tr key={economy.code}>
              <th scope="row" className="sticky left-0 z-10 w-32 min-w-32 border-t border-line bg-surface px-3 text-left text-footnote font-semibold border-r sm:w-36 sm:min-w-36 sm:text-subhead">
                {economy.name}
              </th>
              {columns.map((column) => (
                <Cell key={column.key} economy={economy} column={column} onSelect={onSelect} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-footnote text-ink-2">
      <li className="flex items-center gap-2">
        schlechter
        <span aria-hidden="true" className="flex h-3 w-24 overflow-hidden rounded-chip">
          <span className="flex-1" style={{ background: "color-mix(in srgb, var(--c-bear-ring) 45%, transparent)" }} />
          <span className="flex-1" style={{ background: "color-mix(in srgb, var(--c-bear-ring) 15%, transparent)" }} />
          <span className="flex-1 bg-fill" />
          <span className="flex-1" style={{ background: "color-mix(in srgb, var(--c-bull-ring) 15%, transparent)" }} />
          <span className="flex-1" style={{ background: "color-mix(in srgb, var(--c-bull-ring) 45%, transparent)" }} />
        </span>
        besser
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="inline-block size-3 rounded-thumb bg-fill ring-1 ring-line" />
        grau = veraltet oder ohne Wertung
      </li>
      <li>– = wird nicht erfasst</li>
    </ul>
  );
}

function Detail({ selected, months, onClose }: { selected: Selected | null; months: number; onClose: () => void }) {
  const indicator = selected?.indicator;
  return (
    <Sheet open={selected !== null} onOpenChange={(open) => !open && onClose()} title={indicator ? indicator.label : ""} description={selected?.economy.name}>
      {indicator && (
        <>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <dt className="text-footnote text-ink-2">Aktueller Wert</dt>
            <dd className="num text-title2 font-bold tracking-title">{indicator.value !== null ? formatDecimal(indicator.value, 2) : "–"}</dd>
          </div>
          <div>
            <dt className="text-footnote text-ink-2">{`Änderung (${months} Monate)`}</dt>
            <dd className="num text-title2 font-bold tracking-title">{indicator.change !== null ? formatDelta(indicator.change) : "–"}</dd>
          </div>
          <div className="col-span-2">
            <dt className="mb-1.5 text-footnote text-ink-2">Bewertung: {indicator.fresh ? verdict(indicator.score) : "Daten zu alt für den Score"}</dt>
            <dd><ScoreBar value={indicator.fresh ? indicator.score : null} /></dd>
          </div>
        </dl>
        <p className="mt-4 text-footnote text-ink-2">
          {indicator.date ? `Stand ${formatDateMedium(indicator.date)}. ` : "Keine Beobachtung. "}
          {indicator.higher_is === "bullish" ? "Ein höherer Wert gilt als besser." : "Ein niedrigerer Wert gilt als besser."}
        </p>
        </>
      )}
    </Sheet>
  );
}

export function MacroPage() {
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const { state, reload } = useApi((signal) => fetchMacro(profile, signal), [profile]);
  const profiles = useApi((signal) => fetchProfiles(signal), []);
  const [selected, setSelected] = useState<Selected | null>(null);

  const macro = state.status === "ready" ? state.data : null;
  const columns = useMemo(() => (macro ? heatColumns(macro) : []), [macro]);
  const options = (profiles.state.status === "ready" ? profiles.state.data : [{ key: "swing" as const, label: "Swing" }, { key: "long_term" as const, label: "Langfristig" }]).map((p) => ({ value: p.key, label: p.label }));

  return (
    <>
      <PageHeader title="Makro" subtitle={macro ? `Veränderung über ${macro.change_months} Monate, gemessen an den letzten 10 Jahren` : "Wirtschaftsdaten nach Land"} />
      <div className="flex flex-col gap-4 px-4 sm:px-8">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <SegmentedControl label="Profil" value={profile} onChange={setProfile} options={options} full className="sm:w-72" />
          <span className="flex items-center gap-1 text-footnote text-ink-2">So liest du die Farben <InfoTip term="heatmap" /></span>
        </div>
        <Legend />
        {state.status === "loading" && <Skeleton className="h-96 w-full rounded-card" />}
        {state.status === "error" && <ErrorState what="Die Makrodaten" onRetry={reload} />}
        {macro && (
          <Card variant="group" className="py-1 pr-1">
            {macro.economies.length === 0 ? (
              <div className="p-4">
                <NoData text="Keine Daten – die Quellen liefern noch keine Wirtschaftsdaten." />
              </div>
            ) : (
              <Heatmap economies={macro.economies} columns={columns} onSelect={setSelected} />
            )}
          </Card>
        )}
        <p className="text-footnote text-ink-2">Tippe auf ein Feld für Wert, Änderung und Stand. Quellen: FRED, Eurostat, EZB.</p>
      </div>
      <Detail selected={selected} months={macro?.change_months ?? 3} onClose={() => setSelected(null)} />
    </>
  );
}
