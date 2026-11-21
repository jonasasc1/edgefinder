// Typen und Abrufe der JSON-API (siehe backend/edgefinder/api/schemas.py).
import { setOffline } from "./offline";

export type ProfileKey = "swing" | "long_term";

export type ProfileNotice = { asset_classes: AssetClass[]; level: "info"; text: string };
export type Profile = { key: ProfileKey; label: string; horizon: string; notices?: ProfileNotice[] };

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
  info_only?: boolean;
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
  percentile: number | null;
  estimate: number | null;
  surprise_pct: number | null;
  text: string | null;
  note: string | null;
  next_date: string | null;
  soon: boolean;
  info_only?: boolean;
  counter_trend?: boolean;
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

/** Faktor-Übereinstimmung: wie viele Faktoren (Gewichtsanteil) zeigen in Richtung des Gesamtscores. */
export type Agreement = {
  direction: -1 | 0 | 1;
  total: number;
  bullish: number;
  bearish: number;
  neutral: number;
  same: number;
  weight_share: number | null;
  bullish_share: number;
  bearish_share: number;
  threshold: number;
  high: boolean;
};

export type Scorecard = {
  asset_id: string;
  profile: ProfileKey;
  as_of: string | null;
  signal_threshold: number;
  agreement?: Agreement | null;
  tiles: ScorecardTile[];
  sections: ScorecardSection[];
};

export const fetchScorecard = (assetId: string, profile: ProfileKey, signal?: AbortSignal) =>
  getJson<Scorecard>(`/api/assets/${encodeURIComponent(assetId)}/scorecard?profile=${profile}`, signal);

// --- Konto (Cloudflare Access, siehe backend/edgefinder/api/account.py) ---

import type { Prefs } from "./accountLogic";

export type Me = { email: string; display_name: string; created_at: string; preferences: Prefs; favorites: string[] };

/** Ergebnis von GET /api/me: Konto, „lokal“ (nicht angemeldet, 401/403/404) oder Fehler (Netz, Server). */
export type MeResult = { kind: "ok"; me: Me } | { kind: "local" } | { kind: "error" };

export async function fetchMe(signal?: AbortSignal): Promise<MeResult> {
  try {
    const response = await fetch("/api/me", { cache: "no-store", signal, headers: { Accept: "application/json" } });
    if (response.ok) {
      const me = (await response.json()) as Me;
      return typeof me?.email === "string" ? { kind: "ok", me } : { kind: "local" };
    }
    await response.text().catch(() => ""); // Body verbrauchen, sonst bleibt die Verbindung offen
    return [401, 403, 404].includes(response.status) ? { kind: "local" } : { kind: "error" };
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    return { kind: "error" };
  }
}

async function putJson<T>(path: string, body: unknown, keepalive = false): Promise<T> {
  const response = await fetch(path, {
    method: "PUT",
    cache: "no-store",
    keepalive,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const putPreferences = (patch: Partial<Prefs>, keepalive = false) => putJson<Prefs>("/api/me/preferences", patch, keepalive);
export const putFavorites = (assetIds: string[], keepalive = false) =>
  putJson<{ favorites: string[] }>("/api/me/favorites", { asset_ids: assetIds }, keepalive);

// --- Eichung (docs/calibration.json, siehe backend/edgefinder/backtest/calibration.py) ---

export type Evidence = "belegt" | "schwach" | "kein_vorteil" | "zu_wenig_daten" | "neutral";

/** Kennzahlen einer Zelle (Anteile 0–1, Renditen als Bruch); fehlt n_eff-Daten, stehen nur n und n_eff. */
export type CalCell = {
  n: number;
  n_eff: number;
  up?: number;
  base_up?: number;
  hit?: number | null;
  base_hit?: number | null;
  mean?: number;
  median?: number;
  base_mean?: number;
  edge?: number | null;
  t?: number | null;
  ci?: [number, number];
};
export type CalPeriods = { all: CalCell; train: CalCell; oos: CalCell };
export type CalBucket = { key: string; label: string; low: number; high: number; direction: -1 | 0 | 1; evidence: Evidence } & CalPeriods;

export type CalMeta = {
  available: boolean;
  generated_at: string | null;
  first_date: string | null;
  data_through: string | null;
  train_end: string | null;
  min_t: number | null;
  min_n_eff: number | null;
};

export type CalAgreement = {
  group: "high" | "low";
  threshold: number;
  horizon: number;
  evidence: Evidence;
  other_evidence: Evidence;
  stats: CalPeriods;
  min_t: number | null;
};

export type AssetCalibration = CalMeta & {
  asset_id: string;
  profile: ProfileKey;
  asset_class: AssetClass;
  as_of: string;
  score: number;
  label: string;
  horizon: number | null;
  horizons: number[];
  bucket: { label: string; low: number; high: number; direction: -1 | 0 | 1 } | null;
  evidence: Evidence | null;
  class_evidence: Evidence | null;
  note: "proven" | "weak" | "no_edge" | "few_data" | "neutral" | "missing";
  stats: CalPeriods | null;
  class_directional: CalPeriods | null;
  asset_stats: CalPeriods | null;
  asset_status: "ok" | "zu_wenig_daten" | null;
  asset_min_n_eff: number | null;
  chart: CalBucket[];
  agreement: CalAgreement | null;
};

export type CalSummaryEntry = {
  horizon: number;
  evidence: Evidence;
  n_eff: number | null;
  hit: number | null;
  base_hit: number | null;
  edge: number | null;
  t: number | null;
  edge_train: number | null;
  edge_oos: number | null;
};
export type CalibrationSummary = CalMeta & { profiles: Partial<Record<ProfileKey, Partial<Record<AssetClass, CalSummaryEntry>>>> };

export const fetchCalibration = (assetId: string, profile: ProfileKey, signal?: AbortSignal) =>
  getJson<AssetCalibration>(`/api/assets/${encodeURIComponent(assetId)}/calibration?profile=${profile}`, signal);
export const fetchCalibrationSummary = (signal?: AbortSignal) => getJson<CalibrationSummary>("/api/calibration/summary", signal);
