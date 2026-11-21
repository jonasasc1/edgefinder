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
  | "scoreHistory"
  | "longTermNotice"
  | "calibration"
  | "evidence"
  | "baseRate"
  | "counterTrend"
  | "agreement"
  | "trainOos"
  | "trackrecord"
  | "driftStatus"
  | "factorDrift"
  | "calibratedProgress";

export const TERMS: Record<TermKey, { title: string; text: string }> = {
  trackrecord: {
    title: "Wie lese ich die Bilanz?",
    text: "Die Eichung beschreibt die Vergangenheit, auf der das Modell entworfen wurde. Die Bilanz prüft die Zukunft: Jedes Signal, das das Programm seit dem Start des Live-Betriebs gegeben hat, wird nach Ablauf seines Zeitraums (Handelstage) mit dem tatsächlichen Kurs verglichen. Nur das ist ein echter Test.\n\nGezählt werden nur die wöchentlichen Signale (freitags); tägliche Signale überlappen sich und würden die Zahl unabhängiger Fälle aufblähen. Treffer heißt: Der Kurs bewegte sich in Richtung des Signals. Wichtig ist der Vergleich mit der Basis (Anteil steigender Kurse im gleichen Zeitraum) und der Vorteil: durchschnittliche Rendite in Signalrichtung minus durchschnittliche Rendite aller Fälle, angegeben in Prozentpunkten.\n\nVon wenigen Wochen Daten lässt sich nichts ablesen. Bis genug unabhängige Fälle vorliegen, steht dort „zu früh“. Das ist keine Anlageberatung und keine Prognose.",
  },
  driftStatus: {
    title: "Drift-Status",
    text: "Vergleicht den Live-Vorteil einer Gruppe mit dem Konfidenzband des Vorteils in der Eichung. Zu früh: noch zu wenige unabhängige Fälle oder Wochen. Im Rahmen: der Live-Wert liegt im Band der Eichung. Schwächer/besser: darunter/darüber. Gegenläufig: der Vorteil ist signifikant negativ, die Signale lagen im Schnitt falsch herum. Die Marken sind absichtlich blau/grau: sie sagen etwas über die Prüfung, nicht ob etwas gut oder schlecht ist. Die Schwellen stehen in config.yaml.",
  },
  factorDrift: {
    title: "Faktor-Drift",
    text: "Misst für jeden Faktor (z. B. Trend, Makro), wie gut sein Teilscore die spätere Kursbewegung geordnet hat (Rangkorrelation, IC) und vergleicht das mit dem Backtest. „Gegenläufig“ heißt: live mit falschem Vorzeichen. Das ist nur eine Meldung; Gewichte werden nie automatisch geändert, sondern im Modellpflege-Zyklus mit Freigabe von Jonas geprüft.",
  },
  calibratedProgress: {
    title: "Eichung zu x % belegt",
    text: "Fortschritt zu den festgelegten Kriterien (config.yaml, Abschnitt live.done): je Gruppe genug unabhängige Fälle, genug Monate und Wochen Live-Betrieb, und ein Live-Vorteil im Rahmen der Eichung oder besser. „Geeicht“ heißt nur: Die Aussage wurde belastbar geprüft. Es heißt nicht, dass die Signale profitabel sind; auch „kein Vorteil“ kann belastbar belegt sein.",
  },
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
    text: "Anteil der Long- bzw. Short-Positionen. COT: Long ÷ (Long + Short) der Non-Commercials. Retail: Anteil der Privatanleger-Positionen. Der Long-Anteil allein sagt nichts über die Richtung: Eine Währung kann 80 % Long sein und trotzdem bearish, wenn das für sie historisch wenig ist. Die Pille ist das Signal des Score-Teilscores und beruht auf dem Perzentil der Netto-Position gegen die letzten drei Jahre (Zeile „Perzentil“), nicht auf dem reinen Anteil. Stimmen Long-Anteil und Perzentil nicht überein, steht ein Hinweis in der Zeile.",
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
  longTermNotice: {
    title: "Warum dieser Hinweis?",
    text: "Der Backtest vergleicht frühere Langfrist-Scores von Indizes und Aktien mit der Kursentwicklung danach. Dabei zeigte sich kein verlässlicher Zusammenhang. Die Scores erklären die aktuelle Lage, sagen aber nichts Belastbares über die Zukunft voraus. Die genauen Zahlen stehen in der Karte „Einordnung“ auf der Detailseite jedes Assets.",
  },
  calibration: {
    title: "Wie lese ich die Einordnung?",
    text: "Die Einordnung zeigt, was Scores in genau diesem Bereich in der Vergangenheit gebracht haben: Wie oft stieg der Kurs in den folgenden Tagen, und wie viel im Schnitt? Das ist ein Rückblick auf frühere Daten, keine Vorhersage und keine Anlageberatung.\n\nWichtig ist der Vergleich mit der Basis: In vielen Märkten steigt der Kurs ohnehin in mehr als der Hälfte der Fälle. Erst wenn ein Bereich dauerhaft besser abschneidet als diese Basis, steckt im Score überhaupt eine Information. Ist der Unterschied klein oder wechselt er das Vorzeichen, zeigt der Score dort keinen belegten Vorteil.\n\nDie Beobachtungen überlappen sich (Stichtag für Stichtag laufen die Zeiträume ineinander). Deshalb zählt nicht die Gesamtzahl, sondern die kleinere Zahl unabhängiger Fälle (n_eff). Das Konfidenzband im Diagramm zeigt, wie unsicher der Durchschnitt ist. Training (2013–2019) und Out-of-Sample (2020 bis heute) zeigen, ob ein Zusammenhang auch in einer späteren Marktphase gehalten hat.",
  },
  evidence: {
    title: "Belegt, schwach, kein Vorteil",
    text: "Belegt: Der Score-Bereich schnitt in Gesamt, Training und Out-of-Sample besser ab als die Basis, mit ausreichend vielen unabhängigen Fällen und einem t-Wert von mindestens 2. Schwach belegt: gleiche Richtung, aber zu wenige Fälle oder zu unsicher. Kein belegter Vorteil: Das Vorzeichen wechselt, ist null oder zeigt in die falsche Richtung. Zu wenig Daten: in einem der Zeiträume weniger als 5 unabhängige Fälle. Die Regeln stehen in config.yaml.",
  },
  baseRate: {
    title: "Basisrate",
    text: "Anteil der Fälle, in denen der Kurs im gleichen Zeitraum ohnehin gestiegen ist, egal welchen Score das Asset hatte. Aktien und Indizes steigen langfristig meist; ein bullisher Score muss diese Rate übertreffen, um etwas zu bedeuten.",
  },
  counterTrend: {
    title: "Gegentrend-Signal",
    text: "Der Score erwartet eine Erholung gegen den aktuellen Kurstrend (nach Kursverlusten eine Erholung, nach starkem Anstieg einen Rückschlag). Bei Aktien und Indizes im Swing-Profil liest der Trend-Faktor eine starke Bewegung als überdehnt (Kurzfrist-Umkehr). Das war im Backtest im Schnitt ein schwacher Effekt; bei außergewöhnlichen Einbrüchen kann es ein Regimewechsel sein.",
  },
  agreement: {
    title: "Faktor-Übereinstimmung",
    text: "Wie viele der Faktoren zeigen in dieselbe Richtung wie der Gesamtscore, und welcher Anteil des Gewichts steckt dahinter. Viele übereinstimmende Faktoren wirken überzeugender; im Backtest erhöhte das die Trefferquote aber nicht belastbar (nur bei Aktien im Swing-Profil ein schwacher Hinweis).",
  },
  trainOos: {
    title: "Training und Out-of-Sample",
    text: "Training sind die Jahre 2013–2019, Out-of-Sample (OOS) 2020 bis heute. Die Regeln wurden auf dem Training gewählt und danach an den späteren Daten geprüft. Hält ein Vorteil in beiden Zeiträumen, ist er verlässlicher; wechselt das Vorzeichen, ist er vermutlich Zufall.",
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
  maintain: { label: "Wartung (Eichung)", text: "Wöchentlich: fehlende Backfill-Stichtage nachrechnen, Eichung neu erzeugen, Drift-Bericht." },
  evaluate: { label: "Auswertung (Bilanz)", text: "Täglich: Live-Signale nach Ablauf des Zeitraums gegen den realen Kurs prüfen." },
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
