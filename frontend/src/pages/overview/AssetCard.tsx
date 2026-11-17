import { Link } from "react-router";

import { Badge, Tag } from "../../components/Badge";
import { PressCard } from "../../components/Card";
import { Delta } from "../../components/Delta";
import { ScoreRing } from "../../components/ScoreRing";
import { Tooltip } from "../../components/Tooltip";
import { formatPercent } from "../../lib/format";
import { levelOf, toneOf } from "../../lib/score";
import { CLASS_LABEL, type Row } from "./model";

/** Kachel: Name, Score-Ring, Label, Änderung seit gestern/Woche. */
export function AssetCard({ row }: { row: Row }) {
  const { asset, entry } = row;
  const tone = entry ? toneOf(levelOf(entry.score, entry.label)) : "flat";
  return (
    <PressCard className="h-full">
      <Link
        to={`/asset/${asset.id}`}
        className="flex h-full flex-col rounded-card p-4 outline-offset-2 sm:p-5"
        aria-label={`${asset.id}, ${asset.name}${entry ? `, ${entry.label}` : ", keine Daten"}`}
      >
        <div className="min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-body font-bold tracking-tight">{asset.id}</span>
            <Tag>{CLASS_LABEL[asset.asset_class]}</Tag>
          </div>
          <div className="mt-0.5 line-clamp-2 min-h-10 text-footnote text-ink-2">{asset.name}</div>
        </div>

        <div className="my-3 flex flex-col items-center gap-2.5">
          <ScoreRing score={entry?.score ?? null} label={entry?.label} size="md" />
          {entry ? <Badge tone={tone}>{entry.label}</Badge> : <Badge tone="flat">Keine Daten</Badge>}
        </div>

        <dl className="mt-auto grid grid-cols-2 gap-2 border-t border-line pt-3 text-footnote">
          <div>
            <dt className="text-ink-2">Gestern</dt>
            <dd><Delta value={entry?.change_1d} /></dd>
          </div>
          <div>
            <dt className="text-ink-2">Woche</dt>
            <dd><Delta value={entry?.change_7d} /></dd>
          </div>
        </dl>
        {entry && (
          <Tooltip content="Anteil der Datenquellen, die für diesen Score Werte geliefert haben. Fehlende Quellen werden nicht mitgerechnet.">
            <span className="num mt-2 w-fit cursor-help text-caption text-ink-2">Abdeckung {formatPercent(entry.coverage)}</span>
          </Tooltip>
        )}
      </Link>
    </PressCard>
  );
}
