import { Card } from "../../components/Card";
import { InfoTip } from "../../components/InfoTip";
import { ScoreBar } from "../../components/ScoreBar";
import { SectionTitle } from "../../components/SectionTitle";
import type { GroupKey, ScorecardTile } from "../../lib/api";
import { formatDelta, formatPercent } from "../../lib/format";
import { levelOf, toneOf } from "../../lib/score";
import type { TermKey } from "../../lib/glossary";

const TERM: Record<GroupKey, TermKey> = {
  technical: "groupTechnical",
  sentiment: "groupSentiment",
  institutional: "groupInstitutional",
  macro: "groupMacro",
};

const TEXT = {
  "bull-strong": "text-bull-ink",
  bull: "text-bull-ink",
  flat: "text-ink-2",
  bear: "text-bear-ink",
  "bear-strong": "text-bear-ink",
} as const;

const WORD = { "bull-strong": "stark bullish", bull: "bullish", flat: "neutral", bear: "bearish", "bear-strong": "stark bearish" } as const;

function Tile({ tile }: { tile: ScorecardTile }) {
  const has = tile.score !== null;
  const tone = has ? toneOf(levelOf(tile.score!)) : "flat";
  return (
    <li>
      <Card className="h-full p-4">
        <h3 className="flex items-center gap-1 text-subhead font-semibold">
          {tile.label}
          <InfoTip term={TERM[tile.key]} />
        </h3>
        <p className={`num mt-2 text-title1 font-bold tracking-title ${TEXT[tone]}`}>
          {has ? (
            <>
              <span className="sr-only">Teilscore {tile.label}: </span>
              {formatDelta(tile.score!)}
              <span className="sr-only">, {WORD[tone]}</span>
            </>
          ) : (
            <span className="text-ink-3">–</span>
          )}
        </p>
        <ScoreBar value={has ? tile.score! / 10 : null} className="mt-3" />
        <p className="mt-2.5 text-caption text-ink-2">
          {has ? `${WORD[tone][0]?.toUpperCase()}${WORD[tone].slice(1)} · Gewicht ${formatPercent(tile.weight)}` : "Keine Daten, Gewicht entfällt"}
        </p>
      </Card>
    </li>
  );
}

/** Vier Teilscore-Kacheln (−10 … +10): Technik, Sentiment, Institutionell, Makro bzw. Fundamentals. */
export function GroupTiles({ tiles }: { tiles: ScorecardTile[] }) {
  if (tiles.length === 0) return null;
  return (
    <section aria-labelledby="groups-title">
      <SectionTitle id="groups-title" title="Teilscores nach Gruppe" term="groupScores" />
      <ul className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map((tile) => (
          <Tile key={tile.key} tile={tile} />
        ))}
      </ul>
    </section>
  );
}
