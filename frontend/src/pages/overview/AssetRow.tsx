import { Link } from "react-router";

import { Badge } from "../../components/Badge";
import { Delta } from "../../components/Delta";
import { IconChevron } from "../../components/icons";
import { ScoreRing } from "../../components/ScoreRing";
import { levelOf, toneOf } from "../../lib/score";
import { CLASS_LABEL, type Row } from "./model";

/** Zeile der Listenansicht (iOS-Gruppe): Ring, Name, Label, Änderungen. */
export function AssetRow({ row }: { row: Row }) {
  const { asset, entry } = row;
  const tone = entry ? toneOf(levelOf(entry.score, entry.label)) : "flat";
  return (
    <Link
      to={`/asset/${asset.id}`}
      className="flex min-h-row items-center gap-3 px-4 py-2.5 transition-colors active:bg-fill sm:gap-4 sm:px-5"
    >
      <ScoreRing score={entry?.score ?? null} label={entry?.label} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-body font-semibold tracking-tight">{asset.id}</span>
          <span className="hidden text-caption text-ink-2 sm:inline">{CLASS_LABEL[asset.asset_class]}</span>
        </div>
        <div className="truncate text-footnote text-ink-2">{asset.name}</div>
      </div>
      <div className="hidden w-20 text-right text-footnote sm:block">
        <div className="text-ink-2">Gestern</div>
        <Delta value={entry?.change_1d} />
      </div>
      <div className="hidden w-20 text-right text-footnote sm:block">
        <div className="text-ink-2">Woche</div>
        <Delta value={entry?.change_7d} />
      </div>
      <div className="flex w-24 flex-col items-end gap-1 sm:w-28">
        {entry ? <Badge tone={tone}>{entry.label}</Badge> : <Badge tone="flat">Keine Daten</Badge>}
        <span className="text-footnote sm:hidden"><Delta value={entry?.change_1d} /></span>
      </div>
      <IconChevron size={18} className="shrink-0 text-ink-3" />
    </Link>
  );
}
