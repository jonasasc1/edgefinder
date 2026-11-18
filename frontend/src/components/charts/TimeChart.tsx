import {
  AreaSeries,
  BaselineSeries,
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineType,
  type IChartApi,
  type ISeriesApi,
  type SeriesType,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { cssColor, cssColorAlpha } from "../../lib/chartColors";
import { formatDateMedium } from "../../lib/format";
import { useTheme } from "../../lib/theme";

export type SeriesSpec = {
  id: string;
  name: string;
  /** [ISO-Datum, Wert], aufsteigend */
  data: readonly [string, number][];
  /** Token-Variable, z. B. "--c-series-1" */
  color: string;
  kind?: "line" | "area" | "baseline";
  /** Pane von oben (0 = oberes Diagramm) */
  pane?: number;
  /** Basislinie der Baseline-Reihe (oberhalb grün, unterhalb rot) */
  base?: number;
  format: (value: number) => string;
  /** Stufenlinie statt Kurve (Wochen-/Zweiwochen-Daten) */
  step?: boolean;
};

type Props = {
  series: readonly SeriesSpec[];
  /** Höhe in px (bei mehreren Panes die Gesamthöhe) */
  height?: number;
  /** Anteil der Panes (Summe egal), z. B. [1, 2] */
  paneWeights?: readonly number[];
  /** Beschreibung für Screenreader */
  label: string;
  /** Horizontale Hilfslinie (z. B. 50 % beim Retail-Sentiment) */
  guide?: { value: number; title: string };
};

const formatValue = (spec: SeriesSpec, value: number | undefined) => (value === undefined ? "–" : spec.format(value));

type Hover = { time: string; values: Record<string, number> } | null;

/**
 * Zeitreihen-Diagramm (TradingView Lightweight Charts) in den Farben der Tokens, mit Legende,
 * die beim Darüberfahren/Berühren die Werte des Tages zeigt (sonst die jüngsten).
 */
export function TimeChart({ series, height = 220, paneWeights, label, guide }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const { resolved } = useTheme();
  const [hover, setHover] = useState<Hover>(null);

  const latest = useMemo(() => {
    const values: Record<string, number> = {};
    let time = "";
    for (const s of series) {
      const last = s.data[s.data.length - 1];
      if (last) {
        values[s.id] = last[1];
        if (last[0] > time) time = last[0];
      }
    }
    return { time, values };
  }, [series]);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const text = cssColor("--c-ink-2");
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: text,
        fontFamily: getComputedStyle(document.body).fontFamily,
        fontSize: 11,
        attributionLogo: false,
        panes: { separatorColor: cssColor("--c-line"), enableResize: false },
      },
      grid: { vertLines: { visible: false }, horzLines: { color: cssColor("--c-line") } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.12, bottom: 0.1 } },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true, timeVisible: false },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { color: cssColor("--c-ink-3"), labelVisible: false, style: 3 },
        horzLine: { visible: false, labelVisible: false },
      },
      localization: { locale: "de-DE" },
      handleScale: { mouseWheel: false, pinch: false, axisPressedMouseMove: false },
      handleScroll: { mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false },
    });
    chartRef.current = chart;

    const created: { spec: SeriesSpec; api: ISeriesApi<SeriesType> }[] = [];
    for (const spec of series) {
      const color = cssColor(spec.color);
      const common = {
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: 4,
        priceFormat: { type: "custom" as const, formatter: spec.format, minMove: 0.0001 },
      };
      const pane = spec.pane ?? 0;
      const lineType = spec.step ? LineType.WithSteps : LineType.Simple;
      let api: ISeriesApi<SeriesType>;
      if (spec.kind === "baseline") {
        api = chart.addSeries(
          BaselineSeries,
          {
            ...common,
            baseValue: { type: "price", price: spec.base ?? 0 },
            topLineColor: cssColor("--c-bull-ring"),
            topFillColor1: cssColorAlpha("--c-bull-ring", 0.28),
            topFillColor2: cssColorAlpha("--c-bull-ring", 0.02),
            bottomLineColor: cssColor("--c-bear-ring"),
            bottomFillColor1: cssColorAlpha("--c-bear-ring", 0.02),
            bottomFillColor2: cssColorAlpha("--c-bear-ring", 0.28),
            lineWidth: 2,
            lineType,
          },
          pane,
        );
      } else if (spec.kind === "area") {
        api = chart.addSeries(
          AreaSeries,
          { ...common, lineColor: color, topColor: cssColorAlpha(spec.color, 0.25), bottomColor: cssColorAlpha(spec.color, 0), lineWidth: 2, lineType },
          pane,
        );
      } else {
        api = chart.addSeries(LineSeries, { ...common, color, lineWidth: 2, lineType }, pane);
      }
      api.setData(spec.data.map(([time, value]) => ({ time: time.slice(0, 10) as Time, value })));
      created.push({ spec, api });
    }
    if (guide) {
      created[0]?.api.createPriceLine({ price: guide.value, color: cssColor("--c-ink-3"), lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: guide.title });
    }
    if (paneWeights) chart.panes().forEach((pane, index) => pane.setStretchFactor(paneWeights[index] ?? 1));
    chart.timeScale().fitContent();

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        setHover(null);
        return;
      }
      const values: Record<string, number> = {};
      for (const { spec, api } of created) {
        const point = param.seriesData.get(api) as { value?: number } | undefined;
        if (point?.value !== undefined) values[spec.id] = point.value;
      }
      setHover({ time: String(param.time), values });
    });

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [series, resolved, paneWeights, guide]);

  const shown = hover ?? latest;
  return (
    <figure className="m-0">
      <figcaption className="mb-2 flex min-h-5 flex-wrap items-baseline gap-x-4 gap-y-1 text-footnote">
        {series.map((s) => (
          <span key={s.id} className="inline-flex items-baseline gap-1.5">
            <span aria-hidden="true" className="size-2 self-center rounded-chip" style={{ background: `var(${s.kind === "baseline" ? "--c-ink-2" : s.color})` }} />
            <span className="text-ink-2">{s.name}</span>
            <span className="num font-semibold text-ink">{formatValue(s, shown.values[s.id])}</span>
          </span>
        ))}
        {shown.time && <span className="num ml-auto text-ink-2">{formatDateMedium(shown.time)}</span>}
      </figcaption>
      <div ref={host} role="img" aria-label={label} style={{ height }} className="w-full touch-pan-y" />
    </figure>
  );
}
