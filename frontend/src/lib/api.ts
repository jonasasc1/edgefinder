// Typen und Abrufe der JSON-API (siehe backend/edgefinder/api/schemas.py).
import { setOffline } from "./offline";

export type ProfileKey = "swing" | "long_term";

export type Profile = { key: ProfileKey; label: string; horizon: string };

export type ScoreEntry = {
  date: string;
  score: number;
  label: string;
  coverage: number;
  change_1d: number | null;
  change_7d: number | null;
};

export type AssetClass = "forex" | "index" | "commodity" | "stock";

export type Asset = {
  id: string;
  name: string;
  asset_class: AssetClass;
  scores: Partial<Record<ProfileKey, ScoreEntry>>;
};

export type History = {
  asset_id: string;
  scores: Record<string, [string, number][]>;
  prices: [string, number][];
};

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  // Der Service Worker liefert bei fehlender Verbindung die letzte Antwort und markiert sie.
  setOffline(response.headers.get("x-ef-cached-at"));
  return (await response.json()) as T;
}

export const fetchAssets = (signal?: AbortSignal) => getJson<Asset[]>("/api/assets", signal);
export const fetchProfiles = (signal?: AbortSignal) => getJson<Profile[]>("/api/profiles", signal);
export const fetchHistory = (id: string, days: number, signal?: AbortSignal) =>
  getJson<History>(`/api/assets/${encodeURIComponent(id)}/history?days=${days}`, signal);

// --- Detailseite, Makro, Änderungen, Status ---

export type Component = {
  factor: string;
  subscore: number | null;
  weight: number;
  effective_weight: number;
  reason: string;
  inputs: Record<string, unknown>;
};

export type ProfileDetail = { score: ScoreEntry; components: Component[] };

export type AssetDetail = {
  id: string;
  name: string;
  asset_class: AssetClass;
  last_price: { date: string; close: number; change_1d_pct: number | null } | null;
  profiles: Partial<Record<ProfileKey, ProfileDetail | null>>;
};

export type CotPoint = {
  report_date: string;
  long: number;
  short: number;
  net: number;
  net_pct_oi: number | null;
  open_interest: number | null;
};
export type CotSeries = { contract_code: string; name: string; points: CotPoint[] };
export type Cot = { asset_id: string; series: CotSeries[] };

export type RetailPoint = { observed_at: string; long_pct: number; short_pct: number };
export type AaiiPoint = { week_date: string; bullish: number; neutral: number; bearish: number };
export type Sentiment = { asset_id: string; retail_symbol: string | null; retail: RetailPoint[]; aaii: AaiiPoint[] };

export type MacroIndicator = {
  key: string;
  label: string;
  category: string;
  higher_is: string;
  date: string | null;
  value: number | null;
  change: number | null;
  score: number | null;
  fresh: boolean;
};
export type MacroEconomy = { code: string; name: string; indicators: MacroIndicator[] };
export type Macro = { change_months: number; economies: MacroEconomy[] };

export type Fact = { concept: string; unit: string; period_start: string; period_end: string; value: number; filed: string };
export type Earning = { earnings_date: string; eps_estimate: number | null; eps_actual: number | null; surprise_pct: number | null };
export type ShortInterest = { settlement_date: string; short_interest: number; days_to_cover: number | null };
export type Insider = {
  transaction_date: string;
  owner_name: string;
  owner_title: string | null;
  code: string;
  shares: number;
  price: number | null;
};
export type Fundamentals = {
  asset_id: string;
  kind: "stock" | "macro" | "none";
  facts: Fact[];
  earnings: Earning[];
  short_interest: ShortInterest[];
  insider: Insider[];
  macro: Macro | null;
};

export type Change = {
  asset_id: string;
  name: string;
  asset_class: AssetClass;
  profile: ProfileKey;
  score: number;
  previous_score: number;
  delta: number;
  label: string;
  previous_label: string;
  label_changed: boolean;
};
export type Since = "1d" | "7d";
export type Changes = { since: Since; date: string | null; changes: Change[] };

export type SourceStatus = {
  source: string;
  enabled: boolean;
  last_success: string | null;
  last_run_status: string | null;
  last_run_at: string | null;
  last_error: string | null;
  stale_after_hours: number;
  stale: boolean;
};
export type Status = { now: string; sources: SourceStatus[]; last_score_date: string | null; last_scored_at: string | null };

export type Sparklines = { profile: ProfileKey; days: number; series: Record<string, [string, number][]> };

const id = encodeURIComponent;
export const fetchAssetDetail = (assetId: string, signal?: AbortSignal) => getJson<AssetDetail>(`/api/assets/${id(assetId)}`, signal);
export const fetchCot = (assetId: string, signal?: AbortSignal) => getJson<Cot>(`/api/assets/${id(assetId)}/cot?weeks=156`, signal);
export const fetchSentiment = (assetId: string, signal?: AbortSignal) =>
  getJson<Sentiment>(`/api/assets/${id(assetId)}/sentiment?days=90&weeks=156`, signal);
export const fetchFundamentals = (assetId: string, profile: ProfileKey, signal?: AbortSignal) =>
  getJson<Fundamentals>(`/api/assets/${id(assetId)}/fundamentals?profile=${profile}`, signal);
export const fetchMacro = (profile: ProfileKey, signal?: AbortSignal) => getJson<Macro>(`/api/macro?profile=${profile}`, signal);
export const fetchChanges = (since: Since, signal?: AbortSignal) => getJson<Changes>(`/api/changes?since=${since}`, signal);
export const fetchStatus = (signal?: AbortSignal) => getJson<Status>("/api/status", signal);
export const fetchSparklines = (profile: ProfileKey, days = 30, signal?: AbortSignal) =>
  getJson<Sparklines>(`/api/sparklines?profile=${profile}&days=${days}`, signal);

// --- Scorecard (Detailseite) ---

export type Signal = "bullish" | "bearish" | "neutral";
export type GroupKey = "technical" | "sentiment" | "institutional" | "macro";

export type ScorecardTile = { key: GroupKey; label: string; score: number | null; weight: number; signal: Signal | null; factors: string[] };

export type ScorecardRow = {
  key: string;
  label: string;
  side: string | null;
  unit: string;
  change_unit: string | null;
  value: number | null;
  previous: number | null;
  change: number | null;
  date: string | null;
  signal: Signal | null;
  score: number | null;
  long_pct: number | null;
  short_pct: number | null;
  estimate: number | null;
  surprise_pct: number | null;
  text: string | null;
  note: string | null;
  next_date: string | null;
  soon: boolean;
};

export type ScorecardSection = {
  key: string;
  group: GroupKey;
  label: string;
  kind: "indicator" | "crowd" | "positioning" | "earnings";
  signal: Signal | null;
  score: number | null;
  rows: ScorecardRow[];
  empty_reason: string | null;
  in_score: boolean;
};

export type Scorecard = {
  asset_id: string;
  profile: ProfileKey;
  as_of: string | null;
  signal_threshold: number;
  tiles: ScorecardTile[];
  sections: ScorecardSection[];
};

export const fetchScorecard = (assetId: string, profile: ProfileKey, signal?: AbortSignal) =>
  getJson<Scorecard>(`/api/assets/${encodeURIComponent(assetId)}/scorecard?profile=${profile}`, signal);
