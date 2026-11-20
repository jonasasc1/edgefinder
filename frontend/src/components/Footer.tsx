import { Wordmark } from "./Brand";

/** Fußzeile auf jeder Seite: Wortmarke, Hinweis „Keine Anlageberatung“ und Quellenangabe der Diagramme. */
export function Footer() {
  return (
    <footer className="mx-auto max-w-prose px-4 pb-4 pt-10 text-center text-footnote text-ink-2">
      <div className="mb-3 flex justify-center text-ink">
        <Wordmark size={22} />
      </div>
      <p className="font-semibold text-ink">Keine Anlageberatung</p>
      <p className="mt-1">
        Die Scores fassen öffentliche Daten zusammen (COT, Sentiment, Makro, Trend) und sind keine Empfehlung zum Kauf oder Verkauf.
      </p>
      <p className="mt-1">
        Charts:{" "}
        <a className="underline underline-offset-2" href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
          TradingView Lightweight Charts™
        </a>
      </p>
    </footer>
  );
}
