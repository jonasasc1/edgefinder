import { Link, useNavigate } from "react-router";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { Delta } from "../../components/Delta";
import { Button, EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { IconChevron, IconCompare, IconStar } from "../../components/icons";
import { PageHeader } from "../../components/PageHeader";
import { ScoreRing } from "../../components/ScoreRing";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Skeleton } from "../../components/Skeleton";
import { Sparkline } from "../../components/Sparkline";
import { StarButton } from "../../components/StarButton";
import { fetchProfiles, fetchSparklines, type ProfileKey } from "../../lib/api";
import { useAssets } from "../../lib/assets";
import { MAX_COMPARE, splitFavorites, useFavorites } from "../../lib/favorites";
import { levelOf, toneOf } from "../../lib/score";
import { useApi } from "../../lib/useApi";
import { usePersistentState } from "../../lib/usePersistentState";
import { CLASS_LABEL, toRows, type Row } from "../overview/model";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];

function FavoriteRow({ row, spark }: { row: Row; spark?: [string, number][] }) {
  const { asset, entry } = row;
  const tone = entry ? toneOf(levelOf(entry.score, entry.label)) : "flat";
  return (
    <li className="flex items-center pr-3 sm:pr-4">
      <Link to={`/asset/${asset.id}`} className="flex min-h-row min-w-0 flex-1 items-center gap-3 px-4 py-2.5 transition-colors active:bg-fill sm:gap-4 sm:px-5">
        <ScoreRing score={entry?.score ?? null} label={entry?.label} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-body font-semibold tracking-tight">{asset.id}</span>
            <span className="hidden text-caption text-ink-2 sm:inline">{CLASS_LABEL[asset.asset_class]}</span>
          </div>
          <div className="truncate text-footnote text-ink-2">{asset.name}</div>
        </div>
        {spark && spark.length >= 3 && (
          <div className="hidden w-28 sm:block">
            <Sparkline data={spark} tone={tone === "bull" || tone === "bull-strong" ? "bull" : tone === "bear" || tone === "bear-strong" ? "bear" : "flat"} height={40} label={`Score-Verlauf ${asset.id}, 30 Tage`} />
          </div>
        )}
        <div className="flex w-24 flex-col items-end gap-1 sm:w-28">
          {entry ? <Badge tone={tone}>{entry.label}</Badge> : <Badge tone="flat">Keine Daten</Badge>}
          <span className="text-footnote"><Delta value={entry?.change_1d} /></span>
        </div>
        <IconChevron size={18} className="hidden shrink-0 text-ink-3 sm:block" />
      </Link>
      <StarButton assetId={asset.id} />
    </li>
  );
}

export function FavoritesPage() {
  const favorites = useFavorites();
  const navigate = useNavigate();
  const { state, reload } = useAssets();
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const profiles = useApi((signal) => fetchProfiles(signal), []);
  const sparks = useApi((signal) => fetchSparklines(profile, 30, signal), [profile]);

  const options = (profiles.state.status === "ready" ? profiles.state.data : [{ key: "swing" as const, label: "Swing" }, { key: "long_term" as const, label: "Langfristig" }]).map((p) => ({ value: p.key, label: p.label }));
  const rows = state.status === "ready" ? splitFavorites(toRows(state.assets, profile), (row) => row.asset.id, favorites).pinned : [];
  const sparkData = sparks.state.status === "ready" ? sparks.state.data.series : {};

  return (
    <>
      <PageHeader
        title="Favoriten"
        subtitle={favorites.length > 0 ? `${favorites.length} ${favorites.length === 1 ? "Asset" : "Assets"}, gespeichert auf diesem Gerät` : "Deine Merkliste"}
      />
      <div className="flex flex-col gap-4 px-4 sm:px-8">
        {favorites.length > 0 && (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SegmentedControl label="Profil" value={profile} onChange={setProfile} options={options} full className="sm:w-72" />
            {favorites.length > 1 && (
              <Link
                to={`/vergleich?ids=${favorites.slice(0, MAX_COMPARE).join(",")}`}
                className="flex h-touch items-center justify-center gap-2 rounded-chip bg-surface px-5 text-subhead font-semibold shadow-card ring-1 ring-edge"
              >
                <IconCompare size={18} />
                {favorites.length > MAX_COMPARE ? `Die ersten ${MAX_COMPARE} vergleichen` : "Favoriten vergleichen"}
              </Link>
            )}
          </div>
        )}

        {favorites.length === 0 && (
          <Card>
            <EmptyState
              icon={<IconStar size={26} />}
              title="Noch keine Favoriten"
              text="Tippe auf einer Detailseite auf den Stern, um ein Asset hier zu merken. Deine Favoriten erscheinen auch oben in der Übersicht."
              action={<Button onClick={() => navigate("/")}>Assets ansehen</Button>}
            />
          </Card>
        )}

        {favorites.length > 0 && state.status === "loading" && (
          <Card variant="group">
            <div aria-busy="true" aria-label="Lädt" className="divide-y divide-line">
              {favorites.slice(0, 6).map((id) => (
                <div key={id} className="flex min-h-row items-center gap-3 px-4 py-3">
                  <Skeleton className="size-12 rounded-chip" />
                  <div className="flex-1 space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-3 w-40" /></div>
                </div>
              ))}
            </div>
          </Card>
        )}
        {favorites.length > 0 && state.status === "error" && <ErrorState what="Die Favoriten" onRetry={reload} />}
        {rows.length > 0 && (
          <Card variant="group">
            <ul className="divide-y divide-line">
              {rows.map((row) => (
                <FavoriteRow key={row.asset.id} row={row} spark={sparkData[row.asset.id]} />
              ))}
            </ul>
          </Card>
        )}
        {favorites.length > 0 && <p className="text-footnote text-ink-2">Favoriten liegen nur in diesem Browser (localStorage) und werden nicht synchronisiert.</p>}
      </div>
    </>
  );
}
