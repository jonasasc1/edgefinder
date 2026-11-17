import { AreaSeries, ColorType, createChart, LineType } from "lightweight-charts";
import { useEffect, useRef } from "react";

import { useTheme } from "../lib/theme";

type Props = {
  /** [ISO-Datum, Wert] */
  data: readonly [string, number][];
  tone?: "flat" | "bull" | "bear";
  height?: number;
  label: string;
};

const LINE = { flat: "--c-ink-2", bull: "--c-bull-ring", bear: "--c-bear-ring" } as const;

// Das Chart parst nur Hex/rgb: CSS-Farbe über ein Canvas in #rrggbb umrechnen.
function toHex(color: string): string {
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return color;
  context.fillStyle = color;
  return context.fillStyle;
}

/** Mini-Verlauf (TradingView Lightweight Charts): keine Achsen, kein Gitter, nur die Form. */
export function Sparkline({ data, tone = "flat", height = 64, label }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const { resolved } = useTheme();

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const css = getComputedStyle(document.documentElement);
    const color = toHex(css.getPropertyValue(LINE[tone]).trim());
    const chart = createChart(element, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, attributionLogo: false },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      leftPriceScale: { visible: false },
      rightPriceScale: { visible: false },
      timeScale: { visible: false, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      handleScroll: false,
      handleScale: false,
    });
    const series = chart.addSeries(AreaSeries, {
      lineColor: color,
      lineWidth: 2,
      lineType: LineType.Curved,
      topColor: `${color}47`,
      bottomColor: `${color}00`,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    series.setData(data.map(([time, value]) => ({ time, value })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, tone, resolved]);

  return <div ref={host} role="img" aria-label={label} style={{ height }} className="w-full" />;
}
