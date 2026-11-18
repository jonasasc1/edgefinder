import { useMemo, useState } from "react";
import { Link } from "react-router";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { Delta } from "../../components/Delta";
import { Button, EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { IconChevron, IconSearch } from "../../components/icons";
import { PageHeader } from "../../components/PageHeader";
import { ScoreRing } from "../../components/ScoreRing";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Skeleton } from "../../components/Skeleton";
import { fetchChanges, fetchProfiles, type Change, type ProfileKey, type Since } from "../../lib/api";
import { formatDate, formatScore } from "../../lib/format";
import { levelOf, toneOf } from "../../lib/score";
import { useApi } from "../../lib/useApi";
import { usePersistentState } from "../../lib/usePersistentState";
import { CLASS_LABEL } from "../overview/model";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];
const SINCE_KEYS: readonly Since[] = ["1d", "7d"];
const SINCE_OPTIONS = [
  { value: "1d" as const, label: "Seit gestern" },
  { value: "7d" as const, label: "Seit einer Woche" },
];
const PAGE = 15;

function ChangeRow({ change }: { change: Change }) {
  return (
    <Link to={`/asset/${change.asset_id}`} className="flex min-h-row items-center gap-3 px-4 py-3 transition-colors active:bg-fill sm:gap-4 sm:px-5">
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2" aria-hidden="true">
        <div className="opacity-60"><ScoreRing score={change.previous_score} label={change.previous_label} size="sm" intro={false} /></div>
        <IconChevron size={14} className="text-ink-2" />
        <ScoreRing score={change.score} label={change.label} size="sm" intro={false} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-body font-semibold tracking-tight">{change.asset_id}</span>
          <span className="hidden text-caption text-ink-2 sm:inline">{CLASS_LABEL[change.asset_class]}</span>
        </div>
        <div className="truncate text-footnote text-ink-2">{change.name}</div>
        <span className="sr-only">
          Score von {formatScore(change.previous_score)} auf {formatScore(change.score)}
        </span>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className="text-body"><Delta value={change.delta} /></span>
        {change.label_changed ? (
          <Badge tone={toneOf(levelOf(change.score, change.label))}>{change.label}</Badge>
        ) : (
          <span className="text-caption text-ink-2">{change.label}</span>
        )}
      </div>
      <IconChevron size={18} className="shrink-0 text-ink-3" />
    </Link>
  );
}

function RowSkeletons() {
  return (
    <Card variant="group" >
      <div aria-busy="true" aria-label="Lädt" className="divide-y divide-line">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="flex min-h-row items-center gap-3 px-4 py-3">
            <Skeleton className="size-12 rounded-chip" />
            <div className="flex-1 space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-3 w-40" /></div>
            <Skeleton className="h-6 w-16 rounded-chip" />
          </div>
        ))}
      </div>
    </Card>
  );
}

export function ChangesPage() {
  const [since, setSince] = usePersistentState<Since>("ef-since", "1d", SINCE_KEYS);
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const { state, reload } = useApi((signal) => fetchChanges(since, signal), [since]);
  const profiles = useApi((signal) => fetchProfiles(signal), []);
  const [shown, setShown] = useState(PAGE);

  const data = state.status === "ready" ? state.data : null;
  const rows = useMemo(() => (data ? data.changes.filter((c) => c.profile === profile && Math.abs(c.delta) >= 0.05) : []), [data, profile]);
  const flipped = rows.filter((c) => c.label_changed).length;
  const options = (profiles.state.status === "ready" ? profiles.state.data : [{ key: "swing" as const, label: "Swing" }, { key: "long_term" as const, label: "Langfristig" }]).map((p) => ({ value: p.key, label: p.label }));

  return (
    <>
      <PageHeader title="Änderungen" subtitle={data?.date ? `Größte Bewegungen, Stand ${formatDate(data.date)}` : "Was hat sich geändert?"} />
      <div className="flex flex-col gap-4 px-4 sm:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SegmentedControl label="Vergleichszeitraum" value={since} onChange={(next) => { setSince(next); setShown(PAGE); }} options={SINCE_OPTIONS} full className="sm:w-80" />
          <SegmentedControl label="Profil" value={profile} onChange={(next) => { setProfile(next); setShown(PAGE); }} options={options} full className="sm:w-64" />
        </div>

        {state.status === "loading" && <RowSkeletons />}
        {state.status === "error" && <ErrorState what="Die Änderungen" onRetry={reload} />}

        {data && rows.length === 0 && (
          <Card>
            <EmptyState
              icon={<IconSearch size={26} />}
              title="Keine Veränderungen"
              text={data.changes.length === 0 ? "Für diesen Zeitraum gibt es noch keinen Vergleichswert. Der Score-Verlauf baut sich täglich auf." : "In diesem Zeitraum hat sich bei keinem Asset der Score spürbar bewegt."}
            />
          </Card>
        )}

        {data && rows.length > 0 && (
          <>
            <p className="text-footnote text-ink-2">
              {rows.length} Assets mit Veränderung{flipped > 0 && `, bei ${flipped} wechselte die Einstufung`}. Sortiert nach der Größe der Bewegung.
            </p>
            <Card variant="group">
              <ul className="divide-y divide-line">
                {rows.slice(0, shown).map((change) => (
                  <li key={`${change.asset_id}-${change.profile}`}><ChangeRow change={change} /></li>
                ))}
              </ul>
            </Card>
            {rows.length > shown && (
              <div className="flex justify-center">
                <Button onClick={() => setShown(shown + PAGE)}>Mehr anzeigen ({rows.length - shown})</Button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
