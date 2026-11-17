import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";

import { Button, EmptyState } from "../../components/EmptyState";
import { IconChevronUpDown, IconGrid, IconList, IconSearch, IconSliders, IconWarning } from "../../components/icons";
import { Card } from "../../components/Card";
import { PageHeader } from "../../components/PageHeader";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Sheet } from "../../components/Sheet";
import { ThemeToggle } from "../../components/ThemeToggle";
import type { ProfileKey } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { spring } from "../../lib/motion";
import { usePersistentState } from "../../lib/usePersistentState";
import { AssetCard } from "./AssetCard";
import { AssetRow } from "./AssetRow";
import { Distribution } from "./Distribution";
import {
  CLASS_LABEL,
  countLevels,
  FILTERS,
  SORT_KEYS,
  SORT_OPTIONS,
  sortRows,
  toRows,
  type ClassFilter,
  type SortKey,
} from "./model";
import { CardSkeletons, RowSkeletons } from "./Skeletons";
import { useOverviewData } from "./useOverviewData";

type View = "cards" | "list";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];
const VIEW_OPTIONS = [
  { value: "cards" as const, label: <IconGrid size={18} />, ariaLabel: "Kartenansicht" },
  { value: "list" as const, label: <IconList size={18} />, ariaLabel: "Listenansicht" },
];

export function OverviewPage() {
  const { state, reload } = useOverviewData();
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const [view, setView] = usePersistentState<View>("ef-view", "cards", ["cards", "list"]);
  const [sort, setSort] = usePersistentState<SortKey>("ef-sort", "score-desc", SORT_KEYS);
  const [filter, setFilter] = useState<ClassFilter>("all");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const assets = state.status === "ready" ? state.assets : null;
  const profiles = state.status === "ready" ? state.profiles : null;
  const allRows = useMemo(() => (assets ? toRows(assets, profile) : []), [assets, profile]);
  const rows = useMemo(
    () => sortRows(filter === "all" ? allRows : allRows.filter((row) => row.asset.asset_class === filter), sort),
    [allRows, filter, sort],
  );
  const counts = useMemo(() => countLevels(rows), [rows]);
  const classCount = (key: ClassFilter) => (key === "all" ? allRows.length : allRows.filter((row) => row.asset.asset_class === key).length);
  const stand = allRows.find((row) => row.entry)?.entry?.date;
  const horizon = profiles?.find((p) => p.key === profile)?.horizon;

  const profileOptions = (profiles ?? [
    { key: "swing" as const, label: "Swing", horizon: "" },
    { key: "long_term" as const, label: "Langfristig", horizon: "" },
  ]).map((p) => ({ value: p.key, label: p.label }));

  return (
    <>
      <PageHeader
        title="Übersicht"
        subtitle={stand ? `Stand ${formatDate(stand)}` : "Scores von −10 bis +10"}
        actions={
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Darstellung ändern"
            className="grid size-touch shrink-0 place-items-center rounded-chip bg-surface text-ink-2 shadow-card ring-1 ring-edge lg:hidden"
          >
            <IconSliders size={20} />
          </button>
        }
      />

      <div className="max-lg:glass sticky top-0 z-20 border-b border-line px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] sm:px-8 lg:border-none lg:bg-canvas">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <SegmentedControl label="Profil" value={profile} onChange={setProfile} options={profileOptions} className="w-full sm:w-72" full />
          {horizon && <p className="text-footnote text-ink-2">{horizon}</p>}
        </div>
      </div>

      <div className="flex flex-col gap-5 px-4 pt-4 sm:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <FilterChips value={filter} onChange={setFilter} count={state.status === "ready" ? classCount : undefined} />
          <div className="flex items-center gap-2">
            <label className="relative min-w-0 flex-1 sm:flex-none">
              <span className="sr-only">Sortierung</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SortKey)}
                className="h-touch w-full appearance-none rounded-control bg-surface pl-3.5 pr-9 text-subhead font-medium shadow-card ring-1 ring-edge sm:w-64"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <IconChevronUpDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-2" />
            </label>
            <SegmentedControl label="Ansicht" value={view} onChange={setView} options={VIEW_OPTIONS} />
          </div>
        </div>

        {state.status === "ready" && rows.length > 0 && <Distribution counts={counts} total={rows.length} />}

        {state.status === "loading" && (view === "cards" ? <CardSkeletons /> : <RowSkeletons />)}

        {state.status === "error" && (
          <Card>
            <EmptyState
              icon={<IconWarning size={26} />}
              title="Die Daten konnten nicht geladen werden"
              text="Der Server antwortet nicht. Prüfe die Verbindung und lade die Übersicht neu."
              action={<Button onClick={reload}>Erneut laden</Button>}
            />
          </Card>
        )}

        {state.status === "ready" && rows.length === 0 && (
          <Card>
            <EmptyState
              icon={<IconSearch size={26} />}
              title={allRows.length === 0 ? "Noch keine Scores vorhanden" : `Keine Assets in „${CLASS_LABEL[filter as keyof typeof CLASS_LABEL]}“`}
              text={
                allRows.length === 0
                  ? "Sobald der erste Score-Lauf fertig ist, erscheinen die Assets hier."
                  : "Für diese Auswahl gibt es keine Scores. Zeige wieder alle Assetklassen."
              }
              action={allRows.length === 0 ? <Button onClick={reload}>Neu laden</Button> : <Button onClick={() => setFilter("all")}>Alle anzeigen</Button>}
            />
          </Card>
        )}

        {state.status === "ready" && rows.length > 0 && (
          view === "cards" ? (
            <ul className="asset-grid">
              {rows.map((row) => (
                <motion.li key={row.asset.id} layout="position" transition={spring} className="min-w-0">
                  <AssetCard row={row} />
                </motion.li>
              ))}
            </ul>
          ) : (
            <Card variant="group">
              <ul className="divide-y divide-line">
                <AnimatePresence initial={false}>
                  {rows.map((row) => (
                    <motion.li key={row.asset.id} layout="position" transition={spring}>
                      <AssetRow row={row} />
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </Card>
          )
        )}

        <footer className="mx-auto max-w-prose pb-4 pt-2 text-center text-footnote text-ink-2">
          <p className="font-semibold text-ink">Keine Anlageberatung</p>
          <p className="mt-1">
            Die Scores fassen öffentliche Daten zusammen (COT, Sentiment, Makro, Trend) und sind keine Empfehlung zum Kauf
            oder Verkauf.
          </p>
          <p className="mt-1">
            Charts:{" "}
            <a className="underline underline-offset-2" href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
              TradingView Lightweight Charts™
            </a>
          </p>
        </footer>
      </div>

      <Sheet open={settingsOpen} onOpenChange={setSettingsOpen} title="Darstellung" description="Folgt dem System, wenn du nichts wählst.">
        <ThemeToggle />
      </Sheet>
    </>
  );
}

function FilterChips({ value, onChange, count }: { value: ClassFilter; onChange: (value: ClassFilter) => void; count?: (key: ClassFilter) => number }) {
  return (
    <div role="group" aria-label="Assetklasse" className="scroll-hidden -mx-4 flex gap-2 overflow-x-auto px-4 py-1 sm:mx-0 sm:flex-wrap sm:px-0">
      {FILTERS.map((key) => {
        const active = key === value;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(key)}
            className={`flex h-touch shrink-0 items-center gap-1.5 rounded-chip px-4 text-subhead font-semibold transition-colors ${
              active ? "bg-ink text-canvas" : "bg-surface text-ink shadow-card ring-1 ring-edge"
            }`}
          >
            {key === "all" ? "Alle" : CLASS_LABEL[key]}
            {count && <span className={`num text-footnote font-medium ${active ? "opacity-70" : "text-ink-2"}`}>{count(key)}</span>}
          </button>
        );
      })}
    </div>
  );
}
