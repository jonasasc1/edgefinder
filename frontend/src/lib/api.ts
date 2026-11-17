// Typen und Abrufe der JSON-API (siehe backend/edgefinder/api/schemas.py).

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
  return (await response.json()) as T;
}

export const fetchAssets = (signal?: AbortSignal) => getJson<Asset[]>("/api/assets", signal);
export const fetchProfiles = (signal?: AbortSignal) => getJson<Profile[]>("/api/profiles", signal);
export const fetchHistory = (id: string, days: number, signal?: AbortSignal) =>
  getJson<History>(`/api/assets/${encodeURIComponent(id)}/history?days=${days}`, signal);
