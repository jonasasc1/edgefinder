// Alle Erklärtexte (Tooltips, Erklär-Sheets) und Anzeigenamen an einer Stelle.
// Kurz halten: ein bis drei Sätze, aus Sicht der Nutzer, Fachbegriffe erklären statt voraussetzen.

export type TermKey =
  | "score"
  | "coverage"
  | "weight"
  | "contribution"
  | "profile"
  | "cot"
  | "cotPercentile"
  | "retail"
  | "aaii"
  | "shortInterest"
  | "daysToCover"
  | "seasonality"
  | "trend"
  | "macro"
  | "fundamentals"
  | "earnings"
  | "surprise"
  | "insider"
  | "heatmap"
  | "groupScores"
  | "groupTechnical"
  | "groupSentiment"
  | "groupInstitutional"
  | "groupMacro"
  | "signal"
  | "previousValue"
  | "noForecast"
  | "longShort"
  | "scoreHistory";

export const TERMS: Record<TermKey, { title: string; text: string }> = {
  groupScores: {
    title: "Teilscores nach Gruppe",
    text: "Die Faktoren des Scores in vier Gruppen gebündelt, jeweils von −10 bis +10. Jede Gruppe ist das gewichtete Mittel ihrer Faktoren; „Gewicht“ ist ihr Anteil am Gesamtscore.",
  },
  groupTechnical: {
    title: "Technik",
    text: "Chart-Trend und Saisonalität. Zeigt, wohin der Kurs läuft und wie sich das Asset zu dieser Jahreszeit meist verhalten hat.",
  },
  groupSentiment: {
    title: "Sentiment",
    text: "Stimmung der Anleger: Privatanleger-Positionen (Myfxbook), AAII-Umfrage und bei Aktien Leerverkäufe. Wird meist konträr gelesen, wenn alle gleich liegen.",
  },
  groupInstitutional: {
    title: "Institutionell",
    text: "Positionierung großer Marktteilnehmer: COT-Bericht der Non-Commercials, bei Aktien Insider-Käufe und -Verkäufe.",
  },
  groupMacro: {
    title: "Makro bzw. Fundamentals",
    text: "Wirtschaftsdaten der betroffenen Volkswirtschaft (Wachstum, Inflation, Arbeitsmarkt, Zinsen). Bei Aktien stattdessen Geschäftszahlen (Fundamentals) und Earnings.",
  },
  signal: {
    title: "Signal",
    text: "Bullish, Bearish oder Neutral aus dem Score der Zeile. Ab ±0,15 auf der Skala −1 bis +1 (in config.yaml einstellbar) gilt ein Signal als bullish bzw. bearish.",
  },
  previousValue: {
    title: "Vorwert",
    text: "Wert der vorherigen Veröffentlichung derselben Reihe. Die Änderung ist Wert minus Vorwert; Prozentwerte ändern sich in Prozentpunkten (PP).",
  },
  noForecast: {
    title: "Keine Prognosen",
    text: "Für Makrodaten stehen keine kostenlosen Konsensprognosen zur Verfügung. Darum zeigt die Tabelle Wert, Vorwert, Änderung und Datum statt Forecast und Surprise. Nur bei Earnings gibt es echte Schätzungen.",
  },
  longShort: {
    title: "Long- und Short-Anteil",
    text: "Anteil der Long- bzw. Short-Positionen. COT: Long ÷ (Long + Short) der Non-Commercials. Retail: Anteil der Privatanleger-Positionen. Die Pille zeigt die Lesart des Scores (Perzentil gegen die eigene Historie), nicht den reinen Anteil.",
  },
  scoreHistory: {
    title: "Score-Verlauf",
    text: "Gesamtscore je Tag als Balken um die Nulllinie: grün über 0, rot darunter, kräftiger bei starkem Signal. Der Verlauf wächst täglich.",
  },
  score: {
    title: "Score",
    text: "Gesamtbewertung von −10 (stark bearish) bis +10 (stark bullish). Er fasst die Teilscores nach den Gewichten des gewählten Profils zusammen. Ein Hinweis auf die Datenlage, keine Prognose.",
  },
  coverage: {
    title: "Abdeckung",
    text: "Anteil der Gewichte, für die Daten vorliegen. Fehlt ein Faktor, werden die übrigen Gewichte hochgerechnet. Unter 70 % ist der Score weniger belastbar.",
  },
  weight: {
    title: "Gewicht",
    text: "So stark zählt der Faktor im Gesamtscore. Der Wert ist schon auf die verfügbaren Faktoren umgerechnet; die Summe ergibt 100 %.",
  },
  contribution: {
    title: "Beitrag",
    text: "Punkte, die der Faktor zum Gesamtscore beisteuert (Teilscore × Gewicht × 10). Alle Beiträge zusammen ergeben den Score.",
  },
  profile: {
    title: "Profil",
    text: "Swing gewichtet Trend und Positionierung stärker (Wochen), Langfristig Makro und Fundamentaldaten (Monate).",
  },
  cot: {
    title: "COT-Positionierung",
    text: "Der Commitments-of-Traders-Bericht der US-Aufsicht CFTC zeigt jeden Freitag, wie große Spekulanten (Non-Commercials) positioniert sind. Extreme Positionen kippen oft.",
  },
  cotPercentile: {
    title: "COT-Perzentil",
    text: "Wo die aktuelle Netto-Position im Vergleich zu den letzten drei Jahren liegt. 100 = so long wie nie, 0 = so short wie nie.",
  },
  retail: {
    title: "Retail-Sentiment (konträr)",
    text: "Anteil der privaten Händler, die long bzw. short sind (Myfxbook). Privatanleger liegen an Wendepunkten oft falsch: Sind viele long, werten wir das als bearish – und umgekehrt.",
  },
  aaii: {
    title: "AAII-Umfrage",
    text: "Wöchentliche Umfrage unter US-Privatanlegern, ob sie die Aktien in 6 Monaten höher, gleich oder tiefer sehen. Wird konträr und nur mit geringem Gewicht gelesen.",
  },
  shortInterest: {
    title: "Short Interest",
    text: "Anzahl der Aktien, auf fallende Kurse gewettet wird (FINRA, zweimal im Monat). Ein starker Anstieg gilt als bearish.",
  },
  daysToCover: {
    title: "Days to Cover",
    text: "Wie viele Handelstage Leerverkäufer bräuchten, um ihre Positionen zurückzukaufen. Hohe Werte bedeuten Druck bei steigenden Kursen (Short Squeeze).",
  },
  seasonality: {
    title: "Saisonalität",
    text: "Wie sich das Asset in den letzten Jahren im gleichen Zeitraum des Jahres entwickelt hat. Schwacher Faktor, zählt nur wenig.",
  },
  trend: {
    title: "Trend",
    text: "Abstand des Kurses zum langsamen Durchschnitt, Kreuzung von schnellem und langsamem Durchschnitt und die jüngste Kursveränderung, jeweils an der Schwankung gemessen.",
  },
  macro: {
    title: "Makro",
    text: "Wirtschaftsdaten (Wachstum, Inflation, Arbeitsmarkt, Zinsen). Bewertet wird, ob sich die Daten gegenüber den letzten Monaten besser oder schlechter entwickeln als üblich.",
  },
  fundamentals: {
    title: "Fundamentaldaten",
    text: "Kennzahlen aus den Quartals- und Jahresberichten (SEC): Umsatzwachstum, Gewinnmargen und Bewertung im Vergleich zur eigenen Geschichte.",
  },
  earnings: {
    title: "Earnings",
    text: "Gewinn je Aktie (EPS): Schätzung der Analysten gegen das gemeldete Ergebnis. Positive Überraschungen stützen den Kurs.",
  },
  surprise: {
    title: "Überraschung",
    text: "Abweichung des gemeldeten Gewinns je Aktie von der Analystenschätzung in Prozent.",
  },
  insider: {
    title: "Insider",
    text: "Käufe und Verkäufe von Führungskräften am offenen Markt (SEC Form 4). Käufe wiegen schwerer als Verkäufe, weil Verkäufe viele Gründe haben.",
  },
  heatmap: {
    title: "Heatmap",
    text: "Grün = Der Indikator hat sich zuletzt besser entwickelt als üblich, rot = schlechter. Bei Arbeitslosigkeit und Erstanträgen gilt „weniger“ als besser. Die Zahl ist der aktuelle Wert.",
  },
};

/** Faktoren der Score-Engine: Anzeigename und zugehörige Erklärung. */
export const FACTORS: Record<string, { label: string; term?: TermKey }> = {
  trend: { label: "Trend", term: "trend" },
  cot: { label: "COT-Positionierung", term: "cot" },
  retail_sentiment: { label: "Retail-Sentiment", term: "retail" },
  macro: { label: "Makro", term: "macro" },
  seasonality: { label: "Saisonalität", term: "seasonality" },
  aaii: { label: "AAII-Umfrage", term: "aaii" },
  fundamentals: { label: "Fundamentaldaten", term: "fundamentals" },
  earnings: { label: "Earnings", term: "earnings" },
  short_interest: { label: "Short Interest", term: "shortInterest" },
  insider: { label: "Insider", term: "insider" },
};

export const factorLabel = (key: string) => FACTORS[key]?.label ?? key;

/** Datenquellen (Status-Seite): Name, was sie liefert, und was bei Ausfall passiert. */
export const SOURCES: Record<string, { label: string; text: string }> = {
  cftc: { label: "CFTC (COT)", text: "Positionierung großer Spekulanten, wöchentlich am Freitag." },
  fred: { label: "FRED", text: "US-Wirtschaftsdaten und Zinsen sowie Reihen weiterer Länder." },
  eurostat: { label: "Eurostat", text: "Wirtschaftsdaten für Euroraum, Deutschland und die Schweiz." },
  ecb: { label: "EZB", text: "Leitzins und Renditen im Euroraum." },
  prices: { label: "Kurse (Yahoo Finance)", text: "Tageskurse aller Assets und Earnings-Termine." },
  myfxbook: { label: "Myfxbook", text: "Retail-Sentiment für Forex, Gold und Silber." },
  aaii: { label: "AAII", text: "Wöchentliche Anlegerumfrage für Indizes und Aktien." },
  edgar: { label: "SEC EDGAR", text: "Geschäftszahlen und Insider-Transaktionen der US-Aktien." },
  finra: { label: "FINRA", text: "Short Interest der US-Aktien, zweimal im Monat." },
};

export const sourceLabel = (key: string) => SOURCES[key]?.label ?? key;

/** Kurznamen der Indikatoren in der Makro-Heatmap (Spaltenköpfe). */
export const INDICATOR_SHORT: Record<string, string> = {
  gdp: "BIP",
  industrial: "Industrie",
  retail_sales: "Einzelhandel",
  cpi: "Inflation",
  core_cpi: "Kerninflation",
  unemployment: "Arbeitslosigkeit",
  payrolls: "Beschäftigung",
  jobless: "Erstanträge",
  policy_rate: "Leitzins",
  yield_2y: "Rendite 2J",
  yield_10y: "Rendite 10J",
};

export const CATEGORY_LABEL: Record<string, string> = {
  growth: "Wachstum",
  inflation: "Inflation",
  labor: "Arbeitsmarkt",
  rates: "Zinsen",
};
export const CATEGORY_ORDER = ["growth", "inflation", "labor", "rates"];

/** SEC-Konzepte (us-gaap/dei) in verständlichen Namen. */
export const CONCEPT_LABEL: Record<string, { label: string; kind: "money" | "eps" | "shares" }> = {
  "us-gaap:Revenues": { label: "Umsatz", kind: "money" },
  "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": { label: "Umsatz", kind: "money" },
  "us-gaap:GrossProfit": { label: "Bruttogewinn", kind: "money" },
  "us-gaap:OperatingIncomeLoss": { label: "Operatives Ergebnis", kind: "money" },
  "us-gaap:NetIncomeLoss": { label: "Nettogewinn", kind: "money" },
  "us-gaap:EarningsPerShareDiluted": { label: "Gewinn je Aktie (verwässert)", kind: "eps" },
  "us-gaap:Assets": { label: "Bilanzsumme", kind: "money" },
  "us-gaap:Liabilities": { label: "Verbindlichkeiten", kind: "money" },
  "us-gaap:StockholdersEquity": { label: "Eigenkapital", kind: "money" },
  "us-gaap:CashAndCashEquivalentsAtCarryingValue": { label: "Zahlungsmittel", kind: "money" },
  "us-gaap:LongTermDebt": { label: "Langfristige Schulden", kind: "money" },
  "us-gaap:NetCashProvidedByUsedInOperatingActivities": { label: "Operativer Cashflow", kind: "money" },
  "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": { label: "Investitionen (Capex)", kind: "money" },
  "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding": { label: "Aktien (verwässert)", kind: "shares" },
  "dei:EntityCommonStockSharesOutstanding": { label: "Aktien im Umlauf", kind: "shares" },
};
