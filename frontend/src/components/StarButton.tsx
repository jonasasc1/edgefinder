import { toggleFavorite, useFavorites } from "../lib/favorites";
import { IconStar } from "./icons";

/** Stern: Asset als Favorit merken (nur auf diesem Gerät). */
export function StarButton({ assetId }: { assetId: string }) {
  const favorites = useFavorites();
  const active = favorites.includes(assetId);
  return (
    <button
      type="button"
      onClick={() => toggleFavorite(assetId)}
      aria-pressed={active}
      aria-label={active ? `${assetId} aus Favoriten entfernen` : `${assetId} zu Favoriten hinzufügen`}
      className={`grid size-touch shrink-0 place-items-center rounded-chip bg-surface shadow-card ring-1 ring-edge transition-colors ${
        active ? "text-accent-ink" : "text-ink-2"
      }`}
    >
      <IconStar size={22} filled={active} />
    </button>
  );
}
