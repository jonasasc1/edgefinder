import { useEffect, useState, type ReactNode } from "react";

import { AnimatedNumber } from "../components/AnimatedNumber";
import { Badge, Tag } from "../components/Badge";
import { BrandMark, Wordmark } from "../components/Brand";
import { Card, PressCard } from "../components/Card";
import { Delta } from "../components/Delta";
import { Button } from "../components/EmptyState";
import { BoltLoader } from "../components/fx/BoltLoader";
import { Illustration, type ArtKind } from "../components/illustrations";
import { IconGrid, IconList } from "../components/icons";
import { PageHeader } from "../components/PageHeader";
import { ScoreRing } from "../components/ScoreRing";
import { SegmentedControl } from "../components/SegmentedControl";
import { Sheet } from "../components/Sheet";
import { Skeleton } from "../components/Skeleton";
import { Sparkline } from "../components/Sparkline";
import { ThemeToggle } from "../components/ThemeToggle";
import { Tooltip } from "../components/Tooltip";
import { fetchHistory } from "../lib/api";
import { formatScore } from "../lib/format";
import { useTheme } from "../lib/theme";

// Die Namen der Tokens stehen hier als Tailwind-Klassen; die Hex-Werte nur in design/tokens.css.
const SURFACES = [
  { name: "canvas", cls: "bg-canvas", note: "Seitengrund" },
  { name: "surface", cls: "bg-surface", note: "Karten" },
  { name: "raised", cls: "bg-raised", note: "Sheets" },
  { name: "fill", cls: "bg-fill", note: "Segmente, Chips" },
  { name: "track", cls: "bg-track", note: "Ring-Spur" },
];
const BRAND = [
  { name: "accent", cls: "bg-accent", note: "Strom: Bedienung, Fokus" },
  { name: "arc", cls: "bg-arc", note: "Lichtbogen" },
  { name: "volt", cls: "bg-volt", note: "Blitzkern (nie als Text)" },
  { name: "volt-soft", cls: "bg-volt-soft", note: "Energie-Fläche" },
  { name: "glow", cls: "bg-glow", note: "Glühen, Fokus" },
];
const ARTS: { kind: ArtKind; name: string }[] = [
  { kind: "offline", name: "Offline: leere Batterie" },
  { kind: "error", name: "Fehler: Blitz getrennt" },
  { kind: "miss", name: "404: Blitz ins Leere" },
  { kind: "empty", name: "Leer: Pole ohne Strom" },
];
const INKS = [
  { name: "ink", cls: "text-ink", note: "Text" },
  { name: "ink-2", cls: "text-ink-2", note: "Zweittext" },
  { name: "ink-3", cls: "text-ink-3", note: "nur Deko" },
  { name: "accent-ink", cls: "text-accent-ink", note: "Bedienung" },
];
const SIGNALS = [
  { group: "Bullish", steps: ["bg-bull-soft", "bg-bull-ring", "bg-bull-ring-strong", "bg-bull-solid"], ink: "text-bull-ink" },
  { group: "Neutral", steps: ["bg-flat-soft", "bg-flat-ring", "bg-flat-ink", "bg-flat-ink"], ink: "text-flat-ink" },
  { group: "Bearish", steps: ["bg-bear-soft", "bg-bear-ring", "bg-bear-ring-strong", "bg-bear-solid"], ink: "text-bear-ink" },
];
const STEP_NAMES = ["Fläche", "Ring", "Ring stark", "Gefüllt"];

const TYPE = [
  { cls: "text-giant font-extrabold tracking-title", name: "Giant 76/72 Saira ExtraBold", sample: "+7,2" },
  { cls: "text-largetitle font-extrabold tracking-title", name: "Large Title 34/40 Saira ExtraBold", sample: "Übersicht" },
  { cls: "text-title1 font-bold tracking-title", name: "Title 1 28/34 Bold", sample: "EURUSD" },
  { cls: "text-title3 font-bold tracking-title", name: "Title 3 20/24 Bold", sample: "Marktbild" },
  { cls: "text-body font-semibold tracking-tight", name: "Body 17/22 Semibold", sample: "Euro / US-Dollar" },
  { cls: "text-subhead", name: "Subhead 15/20 Regular", sample: "Scores fassen öffentliche Daten zusammen." },
  { cls: "text-footnote text-ink-2", name: "Footnote 13/18 Regular", sample: "Abdeckung 80 % · Stand 17. November 2026" },
  { cls: "text-caption font-medium text-ink-2", name: "Caption 12/16 Medium", sample: "Forex" },
];

const RING_STATES: { score: number | null; label: string }[] = [
  { score: -10, label: "Stark bearish" },
  { score: -6.4, label: "Stark bearish" },
  { score: -3.2, label: "Bearish" },
  { score: -0.8, label: "Neutral" },
  { score: 0.04, label: "Neutral" },
  { score: 1.9, label: "Neutral" },
  { score: 3.4, label: "Bullish" },
  { score: 7.2, label: "Stark bullish" },
  { score: 10, label: "Stark bullish" },
  { score: null, label: "Keine Daten" },
];

function Section({ title, text, children }: { title: string; text?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-title3 font-bold tracking-title">{title}</h2>
        {text && <p className="mt-0.5 max-w-prose text-subhead text-ink-2">{text}</p>}
      </div>
      {children}
    </section>
  );
}

export function DesignPage() {
  const { resolved } = useTheme();
  const [segment, setSegment] = useState<"a" | "b">("a");
  const [view, setView] = useState<"cards" | "list">("cards");
  const [sheet, setSheet] = useState(false);
  const [demo, setDemo] = useState(4.6);
  const [prices, setPrices] = useState<[string, number][] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchHistory("EURUSD", 90, controller.signal)
      .then((history) => setPrices(history.prices))
      .catch(() => setPrices(null));
    return () => controller.abort();
  }, []);

  const nextDemo = () => {
    const values = [-7.8, -2.4, 0.6, 4.6, 8.9];
    const index = values.indexOf(demo);
    setDemo(values[(index + 1) % values.length] ?? 4.6);
  };

  return (
    <>
      <PageHeader title="Design-System" subtitle={`Tokens und Komponenten, Modus: ${resolved === "dark" ? "dunkel" : "hell"}`} />
      <div className="flex flex-col gap-10 px-4 pt-2 sm:px-8">
        <Section title="Darstellung" text="Folgt dem System; die Wahl wird im Browser gespeichert.">
          <div className="max-w-md"><ThemeToggle /></div>
        </Section>

        <Section title="Farben" text="Grün und Rot tragen Bedeutung (bullish/bearish) in je vier Stufen. Elektro-Blau und Blitzgelb gehören der Marke: Bedienung, Fokus, Energie-Effekte.">
          <Card className="p-4 sm:p-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {SURFACES.map((s) => (
                <div key={s.name}>
                  <div className={`h-16 rounded-control ring-1 ring-line ${s.cls}`} />
                  <div className="mt-1.5 text-footnote font-semibold">{s.name}</div>
                  <div className="text-caption text-ink-2">{s.note}</div>
                </div>
              ))}
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
              {BRAND.map((s) => (
                <div key={s.name}>
                  <div className={`h-12 rounded-control ring-1 ring-line ${s.cls}`} />
                  <div className="mt-1.5 text-footnote font-semibold">{s.name}</div>
                  <div className="text-caption text-ink-2">{s.note}</div>
                </div>
              ))}
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {INKS.map((s) => (
                <div key={s.name} className={`text-title1 font-bold tracking-title ${s.cls}`}>
                  Aa
                  <div className="text-footnote font-semibold text-ink">{s.name}</div>
                  <div className="text-caption font-normal text-ink-2">{s.note}</div>
                </div>
              ))}
            </div>
            <div className="mt-5 flex flex-col gap-4">
              {SIGNALS.map((group) => (
                <div key={group.group}>
                  <div className={`mb-1.5 text-footnote font-semibold ${group.ink}`}>{group.group}</div>
                  <div className="grid grid-cols-4 gap-2">
                    {group.steps.map((step, index) => (
                      <div key={index}>
                        <div className={`h-10 rounded-control ${step}`} />
                        <div className="mt-1 text-caption text-ink-2">{STEP_NAMES[index]}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Section>

        <Section title="Typografie" text="Saira (OFL, eckig-technisch) für Titel und Zahlen, Fließtext in der Systemschrift (SF Pro auf Apple-Geräten), sonst Inter. Alles selbst gehostet, Zahlen tabellarisch.">
          <Card className="divide-y divide-line">
            {TYPE.map((t) => (
              <div key={t.name} className="flex flex-col gap-0.5 px-4 py-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6 sm:px-5">
                <div className={t.cls}>{t.sample}</div>
                <div className="shrink-0 text-caption text-ink-2">{t.name}</div>
              </div>
            ))}
            <div className="num flex flex-col gap-0.5 px-4 py-3 text-subhead sm:px-5">
              <span>1.234,5 / 1.111,1 / 0,0 – Ziffern gleich breit</span>
            </div>
          </Card>
        </Section>

        <Section title="Score-Ring" text="Spannungs-Gauge: 270°-Energiebogen von −10 bis +10, Null oben, mit hellem Kern. Bei Wertänderung entlädt sich ein Blitz entlang des Bogens, ab ±6 knistern Funken.">
          <Card className="p-4 sm:p-5">
            <div className="grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-5">
              {RING_STATES.map((s) => (
                <div key={String(s.score)} className="flex flex-col items-center gap-2">
                  <ScoreRing score={s.score} label={s.label} size="md" />
                  <Badge tone={s.score === null ? "flat" : s.score >= 6 ? "bull-strong" : s.score >= 2 ? "bull" : s.score > -2 ? "flat" : s.score > -6 ? "bear" : "bear-strong"}>
                    {s.label}
                  </Badge>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-end gap-8 border-t border-line pt-5">
              <div className="flex flex-col items-center gap-2"><ScoreRing score={4.6} label="Bullish" size="sm" /><span className="text-caption text-ink-2">Klein (Liste)</span></div>
              <div className="flex flex-col items-center gap-2"><ScoreRing score={-4.6} label="Bearish" size="md" /><span className="text-caption text-ink-2">Mittel (Karte)</span></div>
              <div className="flex flex-col items-center gap-2"><ScoreRing score={demo} size="lg" showLabel label={demo >= 6 ? "Stark bullish" : demo >= 2 ? "Bullish" : demo > -2 ? "Neutral" : demo > -6 ? "Bearish" : "Stark bearish"} /><span className="text-caption text-ink-2">Groß mit Label</span></div>
              <div className="flex flex-col items-start gap-2">
                <Button onClick={nextDemo}>Wert wechseln</Button>
                <span className="text-caption text-ink-2">Ring und Zahl laufen federnd mit, die Zahl blitzt grün (mehr) oder rot (weniger) auf.</span>
              </div>
            </div>
          </Card>
        </Section>

        <Section title="Marke" text="Eine Panzerplatte mit zwei abgeschrägten Ecken und ein monumentales E, dessen mittlerer Arm ein Blitz ist. Dieselbe Platte formt die Karten.">
          <Card className="flex flex-wrap items-center gap-8 p-4 sm:p-6">
            <BrandMark size={96} />
            <div className="flex flex-col gap-3">
              <Wordmark size={40} />
              <Wordmark size={24} />
            </div>
            <p className="max-w-xs text-footnote text-ink-2">Taste „z“ auf dem Desktop lässt einen großen Blitz über den Bildschirm fahren.</p>
          </Card>
        </Section>

        <Section title="Strom-Effekte" text="Lichtbogen am Rand bei Hover und Tap, Glühen am Zeiger, Blitz am Score-Ring, Schimmer beim Laden. Bei reduzierter Bewegung ruht alles.">
          <div className="grid gap-4 sm:grid-cols-3">
            <PressCard className="p-5">
              <div className="font-display text-title3 font-bold">Zap-Karte</div>
              <p className="mt-1 text-footnote text-ink-2">Zeiger darüber bewegen oder antippen: der Lichtbogen läuft einmal um den Rand.</p>
            </PressCard>
            <Card className="flex flex-col justify-center gap-2 p-5">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </Card>
            <Card className="p-2"><BoltLoader label="Ladeanzeige" /></Card>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {ARTS.map((a) => (
              <Card key={a.kind} className="flex flex-col items-center p-3 text-center">
                <Illustration kind={a.kind} />
                <span className="text-caption text-ink-2">{a.name}</span>
              </Card>
            ))}
          </div>
        </Section>

        <Section title="Bedienelemente">
          <Card className="grid gap-6 p-4 sm:grid-cols-2 sm:p-5">
            <div className="flex flex-col gap-2">
              <span className="text-footnote font-semibold">Segmented Control</span>
              <SegmentedControl label="Beispiel" value={segment} onChange={setSegment} options={[{ value: "a", label: "Swing" }, { value: "b", label: "Langfristig" }]} full />
              <SegmentedControl size="sm" className="self-start" label="Ansicht" value={view} onChange={setView} options={[{ value: "cards", label: <IconGrid size={16} />, ariaLabel: "Karten" }, { value: "list", label: <IconList size={16} />, ariaLabel: "Liste" }]} />
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-footnote font-semibold">Badges und Änderung</span>
              <div className="flex flex-wrap gap-2">
                <Badge tone="bull-strong">Stark bullish</Badge>
                <Badge tone="bull">Bullish</Badge>
                <Badge tone="flat">Neutral</Badge>
                <Badge tone="bear">Bearish</Badge>
                <Badge tone="bear-strong">Stark bearish</Badge>
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <Delta value={0.8} /><Delta value={-1.2} /><Delta value={0} /><Tag>Forex</Tag>
              </div>
            </div>
            <div className="flex flex-col items-start gap-2">
              <span className="text-footnote font-semibold">Tooltip und Sheet</span>
              <div className="flex flex-wrap gap-3">
                <Tooltip content="Anteil der Datenquellen, die Werte geliefert haben."><button type="button" className="h-touch rounded-chip bg-fill px-5 text-subhead font-semibold">Abdeckung 80 %</button></Tooltip>
                <Button onClick={() => setSheet(true)}>Sheet öffnen</Button>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-footnote font-semibold">Zahl-Animation</span>
              <button type="button" onClick={nextDemo} className="h-touch w-fit rounded-chip bg-fill px-5 text-title3 font-bold tracking-title">
                <AnimatedNumber value={demo} format={formatScore} />
              </button>
            </div>
          </Card>
        </Section>

        <Section title="Verlauf und Laden" text="Mini-Verlauf mit TradingView Lightweight Charts (EURUSD, 90 Tage, echte Kurse).">
          <Card className="grid gap-5 p-4 sm:grid-cols-2 sm:p-5">
            <div>
              {prices ? <Sparkline data={prices} label="Kursverlauf EURUSD der letzten 90 Tage" height={96} /> : <Skeleton className="h-24" />}
            </div>
            <div className="flex flex-col gap-2" aria-hidden="true">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-48 max-w-full" />
              <Skeleton className="h-4 w-40 max-w-full" />
            </div>
          </Card>
        </Section>
      </div>

      <Sheet open={sheet} onOpenChange={setSheet} title="Beispiel-Sheet" description="Glasfläche, Fokus bleibt im Dialog, Esc schließt.">
        <p className="text-subhead text-ink-2">Sheets nehmen auf dem Handy die untere Hälfte ein, am PC erscheinen sie zentriert.</p>
      </Sheet>
    </>
  );
}
