import { Link, useNavigate, useParams } from "react-router";

import { Badge, Tag } from "../../components/Badge";
import { Card } from "../../components/Card";
import { Delta } from "../../components/Delta";
import { Button, EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { IconBack, IconCompare } from "../../components/icons";
import { InfoTip } from "../../components/InfoTip";
import { PageHeader } from "../../components/PageHeader";
import { ProfileNotices } from "../../components/ProfileNotices";
import { ScoreRing } from "../../components/ScoreRing";
import { SectionTitle } from "../../components/SectionTitle";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Skeleton } from "../../components/Skeleton";
import { StarButton } from "../../components/StarButton";
import { fetchAssetDetail, fetchProfiles, fetchScorecard, type AssetDetail, type ProfileKey, type ProfileNotice } from "../../lib/api";
import { formatDateMedium, formatPct, formatPctSigned, formatPrice } from "../../lib/format";
import { activeNotices } from "../../lib/notices";
import { levelOf, toneOf } from "../../lib/score";
import { useApi } from "../../lib/useApi";
import { usePersistentState } from "../../lib/usePersistentState";
import { CLASS_LABEL } from "../overview/model";
import { CotCard } from "./CotCard";
import { FactorList } from "./FactorList";
import { FundamentalsCard } from "./FundamentalsCard";
import { GroupTiles } from "./GroupTiles";
import { PriceScoreChart } from "./PriceScoreChart";
import { ScorecardTables } from "./ScorecardTables";
import { SentimentCard } from "./SentimentCard";

const PROFILE_KEYS: readonly ProfileKey[] = ["swing", "long_term"];

function Hero({ detail, profile, horizon, notices }: { detail: AssetDetail; profile: ProfileKey; horizon?: string; notices: ProfileNotice[] }) {
  const entry = detail.profiles[profile]?.score;
  const tone = entry ? toneOf(levelOf(entry.score, entry.label)) : "flat";
  const price = detail.last_price;
  return (
    <Card className="p-5 sm:p-6">
      <ProfileNotices notices={notices} gap="mb-5" collapsedGap="mb-0" />
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-10">
        <div className="flex flex-col items-center gap-3">
          <ScoreRing score={entry?.score ?? null} label={entry?.label} size="xl" />
          {entry ? <Badge tone={tone} className="px-3 py-1 text-footnote">{entry.label}</Badge> : <Badge tone="flat">Keine Daten</Badge>}
        </div>
        <div className="w-full flex-1 sm:max-w-xl">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5">
          <div>
            <dt className="text-footnote text-ink-2">Seit gestern</dt>
            <dd className="text-title3 font-bold tracking-title"><Delta value={entry?.change_1d} /></dd>
          </div>
          <div>
            <dt className="text-footnote text-ink-2">Seit einer Woche</dt>
            <dd className="text-title3 font-bold tracking-title"><Delta value={entry?.change_7d} /></dd>
          </div>
          <div>
            <dt className="flex items-center gap-1 text-footnote text-ink-2">
              Abdeckung <InfoTip term="coverage" />
            </dt>
            <dd className="num text-title3 font-bold tracking-title">{entry ? formatPct(entry.coverage * 100, 0) : "–"}</dd>
          </div>
          <div>
            <dt className="text-footnote text-ink-2">Letzter Kurs</dt>
            <dd className="num text-title3 font-bold tracking-title">{price ? formatPrice(price.close) : "–"}</dd>
            {price?.change_1d_pct !== null && price?.change_1d_pct !== undefined && (
              <dd className="num text-footnote font-medium text-ink-2">{formatPctSigned(price.change_1d_pct, 2)} zum Vortag</dd>
            )}
          </div>
        </dl>
        <p className="mt-5 border-t border-line pt-4 text-footnote text-ink-2">
          {entry ? `Stand ${formatDateMedium(entry.date)}. ` : ""}
          {horizon}
        </p>
        </div>
      </div>
    </Card>
  );
}

function Skeletons() {
  return (
    <div className="flex flex-col gap-6 px-4 sm:px-8" aria-busy="true" aria-label="Lädt">
      <Skeleton className="h-80 w-full rounded-card" />
      <div className="grid gap-6 lg:grid-cols-[5fr_7fr]">
        <Skeleton className="h-96 w-full rounded-card" />
        <Skeleton className="h-96 w-full rounded-card" />
      </div>
    </div>
  );
}

export function AssetPage() {
  const { id = "" } = useParams();
  const { state, reload } = useApi((signal) => fetchAssetDetail(id, signal), [id]);
  const profiles = useApi((signal) => fetchProfiles(signal), []);
  const [profile, setProfile] = usePersistentState<ProfileKey>("ef-profile", "swing", PROFILE_KEYS);
  const scorecard = useApi((signal) => fetchScorecard(id, profile, signal), [id, profile]);

  const profileList = profiles.state.status === "ready" ? profiles.state.data : null;
  const options = (profileList ?? [{ key: "swing" as const, label: "Swing", horizon: "" }, { key: "long_term" as const, label: "Langfristig", horizon: "" }]).map((p) => ({ value: p.key, label: p.label }));
  const horizon = profileList?.find((p) => p.key === profile)?.horizon;

  const back = (
    <Link to="/" className="-ml-2 mb-2 inline-flex h-touch items-center gap-1 rounded-control px-2 text-subhead font-medium text-accent-ink">
      <IconBack size={20} />
      Übersicht
    </Link>
  );

  const detail = state.status === "ready" ? state.data : null;
  const failed = state.status === "error" ? state.message : null;
  const title = detail?.id ?? id;

  return (
    <>
      <PageHeader
        before={back}
        title={title}
        subtitle={detail ? <span className="flex flex-wrap items-center gap-x-2">{detail.name}<Tag>{CLASS_LABEL[detail.asset_class]}</Tag></span> : <span className="skeleton inline-block h-4 w-40 rounded-control align-middle" />}
        actions={
          detail && (
            <>
              <Link
                to={`/vergleich?ids=${encodeURIComponent(detail.id)}`}
                aria-label={`${detail.id} vergleichen`}
                className="grid size-touch shrink-0 place-items-center rounded-chip bg-surface text-ink-2 shadow-card ring-1 ring-edge"
              >
                <IconCompare size={20} />
              </Link>
              <StarButton assetId={detail.id} />
            </>
          )
        }
      />

      {state.status === "loading" && <Skeletons />}

      {failed === "HTTP 404" && <UnknownAsset id={id} />}
      {failed !== null && failed !== "HTTP 404" && (
        <div className="px-4 sm:px-8">
          <ErrorState what={`Die Daten zu ${id}`} onRetry={reload} />
        </div>
      )}

      {detail && (
        <div className="flex flex-col gap-6 px-4 sm:px-8">
          <SegmentedControl label="Profil" value={profile} onChange={setProfile} options={options} full className="sm:w-72" />
          <Hero detail={detail} profile={profile} horizon={horizon} notices={activeNotices(profileList, profile, [detail.asset_class])} />

          {scorecard.state.status === "ready" && <GroupTiles tiles={scorecard.state.data.tiles} />}
          <PriceScoreChart assetId={detail.id} profile={profile} />
          {scorecard.state.status === "loading" && <Skeleton className="h-64 w-full rounded-card" />}
          {scorecard.state.status === "error" && <ErrorState what="Die Scorecard" onRetry={scorecard.reload} />}
          {scorecard.state.status === "ready" && <ScorecardTables scorecard={scorecard.state.data} isStock={detail.asset_class === "stock"} />}

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <section aria-labelledby="factors-title">
              <SectionTitle
                id="factors-title"
                title="Faktoren im Detail"
                term="score"
                aside={detail.profiles[profile] ? <span className="text-footnote text-ink-2">Beitrag in Punkten</span> : undefined}
              />
              <Card variant="group">
                {detail.profiles[profile] ? (
                  <FactorList detail={detail.profiles[profile]!} />
                ) : (
                  <EmptyState art="empty" title="Noch kein Score" text="Für dieses Profil liegt noch keine Berechnung vor. Sie erscheint nach dem nächsten Score-Lauf." />
                )}
              </Card>
            </section>

            <div className="flex min-w-0 flex-col gap-6">
              <CotCard assetId={detail.id} assetClass={detail.asset_class} />
              <SentimentCard assetId={detail.id} assetClass={detail.asset_class} />
            </div>
          </div>

          {detail.asset_class === "stock" && <FundamentalsCard assetId={detail.id} profile={profile} isStock /> }
        </div>
      )}
    </>
  );
}

function UnknownAsset({ id }: { id: string }) {
  const navigate = useNavigate();
  return (
    <div className="px-4 sm:px-8">
      <Card>
        <EmptyState
          art="miss"
          title={`„${id}“ gibt es nicht`}
          text="Dieses Asset ist nicht in der Liste. Suche es über die Suche oder gehe zurück zur Übersicht."
          action={<Button onClick={() => navigate("/")}>Zur Übersicht</Button>}
        />
      </Card>
    </div>
  );
}
