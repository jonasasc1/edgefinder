# Backtest-Report

Erzeugt: 2026-11-21T08:16:29+00:00 · Zeitraum der Stichtage: 2013-01-04 bis 2026-11-21 · 732 Stichtage, 62943 Scores (je Asset und Profil) · Handelstage-Abstand der Stichtage ≈ 5.

## Methode und Lesehilfe

- Jeder gespeicherte Score wird mit der Rendite vom letzten Schlusskurs ≤ Stichtag bis `h` Handelstage später verglichen. Der Score kennt nur Daten bis zum Stichtag (Look-Ahead-Schutz der Score-Engine); Renditefenster über den letzten Kurs hinaus entfallen.
- **Trefferquote:** Anteil der Signale mit korrekter Richtung. Signal = Score in einem bullishen bzw. bearishen Bereich (`scoring.labels`, ohne „Neutral“). **Basis (steigend)** ist der Anteil positiver Forward-Renditen über alle Beobachtungen: Indizes und Aktien steigen im Zeitraum überwiegend, eine Trefferquote bullisher Signale ist nur im Vergleich dazu aussagekräftig.
- **Spread:** mittlere Forward-Rendite aller bullishen minus aller bearishen Signale.
- **IC:** Spearman-Rangkorrelation Score ↔ Forward-Rendite (gepoolt über alle Assets und Stichtage); **IC (Querschnitt)** = Mittel der IC je Stichtag über die Assets einer Klasse (nur Tage mit ≥ 5 Assets).
- **t-Werte** sind mit der effektiven Stichprobengröße `n / (h / Abstand)` gerechnet; ein Stern kennzeichnet |t| ≥ 2.
- **Alle Klassen:** IC und Spread sind das n-gewichtete Mittel der Klassenwerte (gepoolt würden unterschiedliche Basisrenditen der Klassen sie verfälschen); Trefferquote und Bereiche sind gepoolt.
- ⚠ = weniger als 30 Beobachtungen: nicht belastbar.

> **Überlappung/Autokorrelation:** Bei wöchentlichen Stichtagen überlappen sich Renditefenster ab einem Horizont über 5 Handelstagen (z. B. 60 Tage: ca. 12 Stichtage teilen sich Kurse). Die Beobachtungen sind nicht unabhängig; n überzeichnet die Aussagekraft, deshalb zusätzlich n_eff. Zudem sind Assets innerhalb einer Klasse stark korreliert (z. B. alle USD-Paare an einem Tag) – die t-Werte bleiben daher optimistisch. Die Gewichte/Parameter sind nicht am Backtest optimiert, trotzdem wurden Schwellen und Faktoren vor der Auswertung gewählt; mehrere Vergleiche (Profile × Klassen × Horizonte) erzeugen einzelne Zufallstreffer.

## Überblick (Kennwert-Horizont je Profil)

| Profil | Klasse | Horizont | n | Signale | Trefferquote | Basis steigend | Spread | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| Swing | Forex | 10 T | 10.108 | 3055 | 48,6 % | 50,6 % | -0,13 % | -0,021 | -1,5 | -0,012 |
| Swing | Indizes | 10 T | 3.610 | 914 | 47,3 % | 60,6 % | +0,67 % | +0,078 | +3,3 * | -0,011 |
| Swing | Rohstoffe | 10 T | 2.888 | 1524 | 48,9 % | 52,5 % | -0,13 % | -0,023 | -0,9 | – |
| Swing | Aktien | 10 T | 14.440 | 6329 | 52,0 % | 57,7 % | +0,42 % | +0,041 | +3,5 * | +0,012 |
| Swing | Alle Klassen | 10 T | 31.046 | 11822 | 50,4 % | 55,2 % | +0,22 % | +0,019 | +2,4 * | -0,005 |
| Langfristig | Forex | 60 T | 9.968 | 3173 | 51,7 % | 50,6 % | +0,06 % | -0,001 | -0,0 | +0,002 |
| Langfristig | Indizes | 60 T | 3.559 | 1366 | 59,6 % | 70,6 % | -4,52 % | -0,139 | -2,4 * | -0,015 |
| Langfristig | Rohstoffe | 60 T | 2.848 | 1504 | 48,5 % | 53,6 % | -1,70 % | -0,030 | -0,5 | – |
| Langfristig | Aktien | 60 T | 14.231 | 9174 | 64,6 % | 67,0 % | -5,82 % | -0,059 | -2,0 * | -0,001 |
| Langfristig | Alle Klassen | 60 T | 30.606 | 15217 | 59,9 % | 60,8 % | -3,37 % | -0,046 | -2,3 * | +0,082 |

## Details je Profil, Klasse und Horizont

### Swing · Forex

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 10.136 | 10.136 | 48,5 % (n=3067) | 50,2 % | +0,01 % | -0,06 % | -1,3 | -0,018 | -1,8 | -0,017 |
| 10 T (Kennwert) | 10.108 | 5.054 | 48,6 % (n=3055) | 50,6 % | +0,03 % | -0,13 % | -1,4 | -0,021 | -1,5 | -0,012 |
| 20 T | 10.080 | 2.520 | 46,7 % (n=3045) | 50,5 % | +0,05 % | -0,27 % | -1,5 | -0,039 | -1,9 | -0,033 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 12 ⚠ | 66,7 % | 66,7 % | +0,68 % | +0,68 % |
| Bullish (+2 bis +6) | 1827 | 50,5 % | 50,5 % | -0,02 % | +0,01 % |
| Neutral (-2 bis +2) | 7053 | (neutral) | 50,1 % | +0,02 % | +0,00 % |
| Bearish (-6 bis -2) | 1212 | 45,6 % | 54,1 % | +0,12 % | +0,11 % |
| Stark bearish (-10 bis -6) | 4 ⚠ | 75,0 % | 25,0 % | -1,02 % | -0,78 % |

### Swing · Indizes

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 3.619 | 3.619 | 49,7 % (n=919) | 57,2 % | +0,27 % | +0,42 % | +2,0 * | +0,052 | +3,2 * | +0,007 |
| 10 T (Kennwert) | 3.610 | 1.805 | 47,3 % (n=914) | 60,6 % | +0,53 % | +0,67 % | +1,7 | +0,078 | +3,3 * | -0,011 |
| 20 T | 3.600 | 900 | 46,1 % (n=912) | 64,1 % | +1,07 % | +1,28 % | +1,8 | +0,076 | +2,3 * | -0,006 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 0 ⚠ | – | – | – | – |
| Bullish (+2 bis +6) | 303 | 65,0 % | 65,0 % | +1,17 % | +1,40 % |
| Neutral (-2 bis +2) | 2696 | (neutral) | 59,9 % | +0,46 % | +0,66 % |
| Bearish (-6 bis -2) | 611 | 38,5 % | 61,5 % | +0,50 % | +0,67 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Swing · Rohstoffe

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 2.896 | 2.896 | 47,7 % (n=1532) | 52,3 % | +0,15 % | -0,19 % | -1,0 | -0,021 | -1,1 | – |
| 10 T (Kennwert) | 2.888 | 1.444 | 48,9 % (n=1524) | 52,5 % | +0,24 % | -0,13 % | -0,3 | -0,023 | -0,9 | – |
| 20 T | 2.880 | 720 | 49,2 % (n=1521) | 51,6 % | +0,49 % | +0,31 % | +0,4 | -0,014 | -0,4 | – |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 6 ⚠ | 16,7 % | 16,7 % | +0,18 % | -0,98 % |
| Bullish (+2 bis +6) | 789 | 51,2 % | 51,2 % | +0,16 % | +0,06 % |
| Neutral (-2 bis +2) | 1364 | (neutral) | 52,9 % | +0,25 % | +0,36 % |
| Bearish (-6 bis -2) | 722 | 47,0 % | 52,9 % | +0,27 % | +0,23 % |
| Stark bearish (-10 bis -6) | 7 ⚠ | 14,3 % | 85,7 % | +2,07 % | +2,99 % |

### Swing · Aktien

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 14.480 | 14.480 | 51,4 % (n=6347) | 55,7 % | +0,48 % | +0,33 % | +2,9 * | +0,030 | +3,6 * | +0,008 |
| 10 T (Kennwert) | 14.440 | 7.220 | 52,0 % (n=6329) | 57,7 % | +0,96 % | +0,42 % | +1,8 | +0,041 | +3,5 * | +0,012 |
| 20 T | 14.400 | 3.600 | 50,7 % (n=6316) | 60,4 % | +1,95 % | +0,63 % | +1,3 | +0,038 | +2,3 * | +0,009 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 36 | 61,1 % | 61,1 % | +0,47 % | +1,18 % |
| Bullish (+2 bis +6) | 3366 | 59,7 % | 59,7 % | +1,23 % | +1,22 % |
| Neutral (-2 bis +2) | 8111 | (neutral) | 57,2 % | +0,90 % | +0,77 % |
| Bearish (-6 bis -2) | 2895 | 43,2 % | 56,6 % | +0,79 % | +0,59 % |
| Stark bearish (-10 bis -6) | 32 | 34,4 % | 65,6 % | +2,23 % | +1,28 % |

### Swing · Alle Klassen

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 31.131 | 31.131 | 50,1 % (n=11865) | 53,8 % | +0,27 % | +0,16 % | – | +0,012 | +2,1 * | -0,004 |
| 10 T (Kennwert) | 31.046 | 15.523 | 50,4 % (n=11822) | 55,2 % | +0,54 % | +0,22 % | – | +0,019 | +2,4 * | -0,005 |
| 20 T | 30.960 | 7.740 | 49,1 % (n=11794) | 56,8 % | +1,09 % | +0,38 % | – | +0,013 | +1,1 | -0,015 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 54 | 57,4 % | 57,4 % | +0,49 % | +0,50 % |
| Bullish (+2 bis +6) | 6285 | 56,2 % | 56,2 % | +0,73 % | +0,42 % |
| Neutral (-2 bis +2) | 19224 | (neutral) | 54,7 % | +0,47 % | +0,29 % |
| Bearish (-6 bis -2) | 5440 | 43,7 % | 56,1 % | +0,54 % | +0,37 % |
| Stark bearish (-10 bis -6) | 43 | 34,9 % | 65,1 % | +1,90 % | +1,19 % |

### Langfristig · Forex

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 10.080 | 2.520 | 49,6 % (n=3200) | 50,5 % | +0,05 % | -0,07 % | -0,4 | -0,006 | -0,3 | -0,012 |
| 60 T (Kennwert) | 9.968 | 831 | 51,7 % (n=3173) | 50,6 % | +0,14 % | +0,06 % | +0,1 | -0,001 | -0,0 | +0,002 |
| 120 T | 9.800 | 408 | 51,9 % (n=3090) | 50,6 % | +0,26 % | +0,53 % | +0,5 | +0,024 | +0,5 | +0,005 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 30 | 63,3 % | 63,3 % | +2,23 % | +1,97 % |
| Bullish (+2 bis +6) | 2118 | 51,8 % | 51,8 % | +0,17 % | +0,13 % |
| Neutral (-2 bis +2) | 6795 | (neutral) | 50,5 % | +0,12 % | +0,04 % |
| Bearish (-6 bis -2) | 1020 | 51,4 % | 48,6 % | +0,13 % | -0,15 % |
| Stark bearish (-10 bis -6) | 5 ⚠ | 20,0 % | 80,0 % | +1,40 % | +2,10 % |

### Langfristig · Indizes

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 3.600 | 900 | 55,4 % (n=1382) | 64,1 % | +1,07 % | -2,34 % | -3,4 * | -0,095 | -2,9 * | +0,017 |
| 60 T (Kennwert) | 3.559 | 297 | 59,6 % (n=1366) | 70,6 % | +3,22 % | -4,52 % | -2,4 * | -0,139 | -2,4 * | -0,015 |
| 120 T | 3.495 | 146 | 59,4 % (n=1345) | 75,5 % | +6,43 % | -7,27 % | -2,1 * | -0,154 | -1,9 | -0,033 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 25 ⚠ | 88,0 % | 88,0 % | +9,96 % | +6,79 % |
| Bullish (+2 bis +6) | 1058 | 69,8 % | 69,8 % | +2,06 % | +2,69 % |
| Neutral (-2 bis +2) | 2193 | (neutral) | 69,4 % | +3,24 % | +3,60 % |
| Bearish (-6 bis -2) | 283 | 19,1 % | 80,9 % | +6,76 % | +6,39 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Langfristig · Rohstoffe

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 2.880 | 720 | 48,1 % (n=1515) | 51,6 % | +0,49 % | -0,12 % | -0,2 | -0,031 | -0,8 | – |
| 60 T (Kennwert) | 2.848 | 237 | 48,5 % (n=1504) | 53,6 % | +2,05 % | -1,70 % | -0,7 | -0,030 | -0,5 | – |
| 120 T | 2.796 | 116 | 51,8 % (n=1482) | 54,7 % | +3,95 % | +1,61 % | +0,3 | +0,029 | +0,3 | – |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 3 ⚠ | 0,0 % | 0,0 % | -12,21 % | -11,46 % |
| Bullish (+2 bis +6) | 781 | 56,1 % | 56,1 % | +1,71 % | +1,90 % |
| Neutral (-2 bis +2) | 1344 | (neutral) | 49,1 % | +1,58 % | -0,24 % |
| Bearish (-6 bis -2) | 693 | 41,0 % | 59,0 % | +3,32 % | +2,11 % |
| Stark bearish (-10 bis -6) | 27 ⚠ | 29,6 % | 70,4 % | +4,21 % | +3,16 % |

### Langfristig · Aktien

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 14.391 | 3.598 | 58,7 % (n=9285) | 60,4 % | +1,95 % | -1,67 % | -1,5 | -0,044 | -2,6 * | +0,015 |
| 60 T (Kennwert) | 14.231 | 1.186 | 64,6 % (n=9174) | 67,0 % | +5,98 % | -5,82 % | -1,5 | -0,059 | -2,0 * | -0,001 |
| 120 T | 13.971 | 582 | 70,0 % (n=9045) | 72,7 % | +12,33 % | -12,56 % | -1,1 | -0,040 | -1,0 | +0,000 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 909 | 62,9 % | 62,9 % | +6,15 % | +3,92 % |
| Bullish (+2 bis +6) | 7937 | 66,2 % | 66,2 % | +5,43 % | +4,31 % |
| Neutral (-2 bis +2) | 5057 | (neutral) | 68,7 % | +6,46 % | +5,42 % |
| Bearish (-6 bis -2) | 328 | 29,6 % | 70,4 % | +11,32 % | +7,01 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Langfristig · Alle Klassen

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 30.951 | 7.738 | 55,4 % (n=15382) | 56,8 % | +1,09 % | -1,08 % | – | -0,036 | -3,2 * | +0,053 |
| 60 T (Kennwert) | 30.606 | 2.550 | 59,9 % (n=15217) | 60,8 % | +3,39 % | -3,37 % | – | -0,046 | -2,3 * | +0,082 |
| 120 T | 30.062 | 1.253 | 63,5 % (n=14962) | 64,1 % | +6,93 % | -6,36 % | – | -0,026 | -0,9 | +0,126 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 967 | 63,4 % | 63,4 % | +6,07 % | +3,80 % |
| Bullish (+2 bis +6) | 11894 | 63,3 % | 63,3 % | +3,95 % | +2,53 % |
| Neutral (-2 bis +2) | 15389 | (neutral) | 59,1 % | +2,78 % | +1,22 % |
| Bearish (-6 bis -2) | 2324 | 41,3 % | 58,7 % | +3,47 % | +1,31 % |
| Stark bearish (-10 bis -6) | 32 | 28,1 % | 71,9 % | +3,77 % | +2,88 % |

## Faktoren (IC je Teilscore, Kennwert-Horizont)

Hinweis für Tuning-Kandidaten, keine Gewichtsänderung ohne Jonas. IC nur über Stichtage, an denen der Faktor verfügbar war.

### Swing (Horizont 10 T)

| Klasse | Faktor | Gewicht | Verfügbar | n | IC | t |
|---|---|---|---|---|---|---|
| Forex | COT | 25 % | 100 % | 10108 | -0,027 | -1,9 |
| Forex | Retail-Sentiment | 20 % | 0 % | 0 | – | – |
| Forex | Makro | 15 % | 94 % | 9521 | +0,010 | +0,7 |
| Forex | Trend | 30 % | 100 % | 10108 | -0,032 | -2,3 * |
| Forex | Saisonalität | 10 % | 87 % | 8736 | +0,029 | +1,9 |
| Indizes | COT | 20 % | 80 % | 2888 | -0,016 | -0,6 |
| Indizes | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Indizes | Makro | 15 % | 96 % | 3460 | -0,026 | -1,1 |
| Indizes | Trend | 35 % | 100 % | 3610 | +0,120 | +5,1 * |
| Indizes | Saisonalität | 10 % | 87 % | 3120 | +0,016 | +0,6 |
| Indizes | AAII | 15 % | 2 % | 10 | -0,453 | -0,9 |
| Rohstoffe | COT | 30 % | 100 % | 2888 | -0,021 | -0,8 |
| Rohstoffe | Retail-Sentiment | 15 % | 0 % | 0 | – | – |
| Rohstoffe | Makro | 10 % | 100 % | 2888 | -0,043 | -1,6 |
| Rohstoffe | Trend | 35 % | 100 % | 2888 | -0,014 | -0,5 |
| Rohstoffe | Saisonalität | 10 % | 87 % | 2496 | -0,003 | -0,1 |
| Aktien | Fundamentals | 15 % | 0 % | 0 | – | – |
| Aktien | Earnings | 20 % | 43 % | 6051 | +0,003 | +0,2 |
| Aktien | Trend | 30 % | 100 % | 14440 | +0,057 | +4,8 * |
| Aktien | Short Interest | 10 % | 14 % | 1840 | +0,010 | +0,3 |
| Aktien | Insider | 10 % | 0 % | 0 | – | – |
| Aktien | Saisonalität | 5 % | 86 % | 12454 | +0,017 | +1,4 |
| Aktien | AAII | 10 % | 2 % | 40 | -0,243 | -1,1 |

### Langfristig (Horizont 60 T)

| Klasse | Faktor | Gewicht | Verfügbar | n | IC | t |
|---|---|---|---|---|---|---|
| Forex | COT | 25 % | 100 % | 9968 | -0,004 | -0,1 |
| Forex | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Forex | Makro | 40 % | 93 % | 9295 | -0,005 | -0,1 |
| Forex | Trend | 20 % | 100 % | 9968 | +0,007 | +0,2 |
| Forex | Saisonalität | 10 % | 87 % | 8596 | -0,021 | -0,6 |
| Indizes | COT | 15 % | 80 % | 2847 | -0,034 | -0,5 |
| Indizes | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Indizes | Makro | 35 % | 93 % | 3303 | -0,153 | -2,6 * |
| Indizes | Trend | 25 % | 100 % | 3559 | -0,108 | -1,9 |
| Indizes | Saisonalität | 10 % | 87 % | 3069 | +0,021 | +0,3 |
| Indizes | AAII | 10 % | 2 % | 0 | – | – |
| Rohstoffe | COT | 30 % | 100 % | 2848 | -0,035 | -0,5 |
| Rohstoffe | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Rohstoffe | Makro | 25 % | 99 % | 2812 | -0,076 | -1,2 |
| Rohstoffe | Trend | 30 % | 100 % | 2848 | +0,009 | +0,1 |
| Rohstoffe | Saisonalität | 10 % | 87 % | 2456 | +0,023 | +0,3 |
| Aktien | Fundamentals | 35 % | 0 % | 0 | – | – |
| Aktien | Earnings | 15 % | 43 % | 5851 | -0,055 | -1,2 |
| Aktien | Trend | 20 % | 100 % | 14231 | -0,025 | -0,9 |
| Aktien | Short Interest | 5 % | 13 % | 1520 | +0,097 | +1,1 |
| Aktien | Insider | 10 % | 0 % | 0 | – | – |
| Aktien | Saisonalität | 5 % | 86 % | 12254 | -0,031 | -1,0 |
| Aktien | AAII | 10 % | 2 % | 0 | – | – |

## Stabilität nach Jahr (IC, Kennwert-Horizont)

Zelle: IC (Anzahl Beobachtungen). Jahre mit weniger Beobachtungen als die Schwelle sind mit ⚠ markiert.

### Swing (Horizont 10 T)

| Klasse | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Forex | +0,04 (728) | +0,12 (728) | -0,01 (728) | +0,04 (742) | -0,11 (728) | -0,04 (728) | -0,08 (728) | +0,02 (728) | -0,10 (742) | +0,05 (728) | -0,15 (728) | -0,13 (728) | -0,09 (728) | -0,07 (616) |
| Indizes | +0,16 (260) | +0,13 (260) | +0,02 (260) | -0,00 (265) | +0,12 (260) | +0,07 (260) | +0,14 (260) | +0,04 (260) | +0,15 (265) | +0,13 (260) | +0,18 (260) | +0,17 (260) | +0,02 (260) | +0,13 (220) |
| Rohstoffe | -0,06 (208) | -0,12 (208) | -0,13 (208) | -0,23 (212) | -0,29 (208) | -0,04 (208) | +0,07 (208) | +0,01 (208) | -0,21 (212) | -0,07 (208) | -0,25 (208) | -0,01 (208) | +0,13 (208) | +0,01 (176) |
| Aktien | +0,10 (1040) | +0,11 (1040) | +0,08 (1040) | +0,07 (1060) | +0,20 (1040) | +0,05 (1040) | +0,07 (1040) | +0,07 (1040) | +0,03 (1060) | +0,02 (1040) | -0,01 (1040) | +0,09 (1040) | +0,09 (1040) | +0,03 (880) |
| Alle Klassen | +0,01 (2236) | +0,05 (2236) | +0,02 (2236) | +0,01 (2279) | -0,04 (2236) | +0,01 (2236) | +0,02 (2236) | +0,04 (2236) | +0,02 (2279) | +0,02 (2236) | -0,04 (2236) | +0,04 (2236) | +0,08 (2236) | +0,02 (1892) |

### Langfristig (Horizont 60 T)

| Klasse | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Forex | +0,23 (728) | +0,25 (728) | -0,11 (728) | +0,09 (742) | -0,18 (728) | -0,27 (728) | -0,43 (728) | +0,03 (728) | +0,10 (742) | +0,13 (728) | -0,07 (728) | -0,23 (728) | -0,35 (728) | +0,32 (476) |
| Indizes | -0,01 (260) | -0,27 (260) | -0,04 (260) | -0,01 (265) | -0,10 (260) | -0,33 (260) | -0,24 (260) | -0,45 (260) | -0,21 (265) | -0,35 (260) | -0,15 (260) | -0,22 (260) | -0,19 (260) | -0,14 (169) |
| Rohstoffe | -0,11 (208) | -0,43 (208) | -0,28 (208) | -0,42 (212) | -0,10 (208) | -0,22 (208) | -0,15 (208) | -0,27 (208) | -0,24 (212) | -0,31 (208) | -0,35 (208) | -0,19 (208) | +0,35 (208) | -0,09 (136) |
| Aktien | +0,00 (1031) | -0,02 (1040) | -0,05 (1040) | -0,13 (1060) | +0,13 (1040) | -0,19 (1040) | -0,14 (1040) | -0,20 (1040) | -0,17 (1060) | -0,19 (1040) | -0,12 (1040) | -0,06 (1040) | -0,04 (1040) | +0,01 (680) |
| Alle Klassen | +0,20 (2227) | +0,14 (2236) | +0,02 (2236) | -0,02 (2279) | +0,20 (2236) | -0,10 (2236) | -0,02 (2236) | -0,03 (2236) | +0,11 (2279) | -0,13 (2236) | +0,06 (2236) | +0,10 (2236) | -0,01 (2236) | +0,07 (1461) |

## Abdeckung je Zeitraum

Anteil der Scores (Profil Swing), in denen der Faktor einen Wert lieferte; Gewichte fehlender Faktoren werden renormiert. Retail-Sentiment, AAII und Short Interest haben keine bzw. kaum Historie vor 2024-11, COT reicht 15 Jahre zurück (ab 2013).

### Forex

| Jahr | Scores | Ø Abdeckung | COT | Makro | Retail-Sentiment | Saisonalität | Trend |
|---|---|---|---|---|---|---|---|
| 2013 | 728 | 64 % | 100 % | 61 % | 0 % | 0 % | 100 % |
| 2014 | 728 | 65 % | 100 % | 59 % | 0 % | 12 % | 100 % |
| 2015 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2016 | 742 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2017 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2018 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2019 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2020 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2021 | 742 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2022 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2023 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2024 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2025 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2026 | 756 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |

### Indizes

| Jahr | Scores | Ø Abdeckung | AAII | COT | Makro | Retail-Sentiment | Saisonalität | Trend |
|---|---|---|---|---|---|---|---|---|
| 2013 | 260 | 60 % | 0 % | 80 % | 60 % | 0 % | 0 % | 100 % |
| 2014 | 260 | 64 % | 0 % | 80 % | 82 % | 0 % | 12 % | 100 % |
| 2015 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2016 | 265 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2017 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2018 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2019 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2020 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2021 | 265 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2022 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2023 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2024 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2025 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2026 | 270 | 79 % | 22 % | 80 % | 100 % | 0 % | 100 % | 100 % |

### Rohstoffe

| Jahr | Scores | Ø Abdeckung | COT | Makro | Retail-Sentiment | Saisonalität | Trend |
|---|---|---|---|---|---|---|---|
| 2013 | 208 | 75 % | 100 % | 100 % | 0 % | 0 % | 100 % |
| 2014 | 208 | 76 % | 100 % | 100 % | 0 % | 12 % | 100 % |
| 2015 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2016 | 212 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2017 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2018 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2019 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2020 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2021 | 212 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2022 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2023 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2024 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2025 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2026 | 216 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |

### Aktien

| Jahr | Scores | Ø Abdeckung | AAII | Earnings | Fundamentals | Insider | Saisonalität | Short Interest | Trend |
|---|---|---|---|---|---|---|---|---|---|
| 2013 | 1040 | 30 % | 0 % | 0 % | 0 % | 0 % | 0 % | 0 % | 100 % |
| 2014 | 1040 | 31 % | 0 % | 0 % | 0 % | 0 % | 11 % | 0 % | 100 % |
| 2015 | 1040 | 35 % | 0 % | 0 % | 0 % | 0 % | 98 % | 0 % | 100 % |
| 2016 | 1060 | 35 % | 0 % | 0 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2017 | 1040 | 35 % | 0 % | 0 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2018 | 1040 | 35 % | 0 % | 0 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2019 | 1040 | 35 % | 0 % | 0 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2020 | 1040 | 35 % | 0 % | 2 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2021 | 1060 | 54 % | 0 % | 94 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2022 | 1040 | 55 % | 0 % | 100 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2023 | 1040 | 55 % | 0 % | 100 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2024 | 1040 | 55 % | 0 % | 100 % | 0 % | 0 % | 100 % | 0 % | 100 % |
| 2025 | 1040 | 64 % | 0 % | 100 % | 0 % | 0 % | 100 % | 92 % | 100 % |
| 2026 | 1080 | 67 % | 22 % | 100 % | 0 % | 0 % | 100 % | 100 % | 100 % |

## Anhang: Überarbeitung des Trend-Faktors (2026-11-18)

**Anlass:** Der erste Backtest zeigte für Indizes und Aktien einen signifikant negativen IC des
Trend-Faktors (Kurzfrist-Umkehr: der Trend-Score korreliert 0,86–0,92 mit der Vorperformance, diese
negativ mit der Forward-Rendite).

**Verfahren:** höchstens drei Varianten, **gewählt auf dem Trainingszeitraum 2013–2019**, danach
einmalig auf **2020 bis heute (Out-of-Sample)** geprüft. Alle anderen Faktoren und Gewichte blieben
unverändert (Teilscores aus dem Backfill, nur Trend ersetzt, Gewichte renormiert). Kennwert-Horizont
(Swing 10 T, Langfristig 60 T), wöchentliche Stichtage, IC = Spearman des Gesamtscores; t-Werte mit
effektiver Stichprobengröße (n_eff = n / (h / 5)). Die Zahlen unten sind IC des **Gesamtscores**.

| Profil · Klasse | Variante | IC Training (t) | IC Out-of-Sample (t) | n_eff OOS |
|---|---|---|---|---|
| Swing · Indizes | Basis (Trend) | -0,114 (-3,5) | -0,072 (-2,1) | 892 |
| Swing · Indizes | V1 Trend-Gewicht × 0,5 | -0,089 (-2,7) | -0,047 (-1,4) | 892 |
| Swing · Indizes | **V2 Umkehr (−Trend)** | **+0,074 (+2,2)** | **+0,081 (+2,4)** | 892 |
| Swing · Aktien | Basis (Trend) | -0,073 (-4,4) | -0,036 (-2,1) | 3570 |
| Swing · Aktien | V1 Trend-Gewicht × 0,5 | -0,070 (-4,3) | -0,027 (-1,6) | 3570 |
| Swing · Aktien | **V2 Umkehr (−Trend)** | **+0,077 (+4,6)** | **+0,022 (+1,3)** | 3570 |
| Langfristig · Indizes | Basis | -0,018 (-0,2) | -0,263 (-3,3) | 144 |
| Langfristig · Indizes | V3 12-1-Monats-Momentum | -0,032 (-0,4) | -0,248 (-3,1) | 144 |
| Langfristig · Aktien | Basis | -0,029 (-0,7) | -0,085 (-2,1) | 578 |
| Langfristig · Aktien | V3 12-1-Monats-Momentum | -0,041 (-1,0) | -0,051 (-1,2) | 578 |

**Entscheidung**
- **V2 übernommen (nur Swing, Indizes und Aktien):** Trend-Teilscore = −(bisheriger Trend-Score),
  konfiguriert über `reversal_classes: [index, stock]` im Swing-Profil. Im Training klar positiv
  (Aktien t = 4,6; Indizes t = 2,2) und Out-of-Sample gleichgerichtet besser als die Basis
  (Indizes +0,081, signifikant; Aktien +0,022, nur schwach positiv, aber +0,058 gegenüber der Basis).
  Ökonomisch plausibel: die Kurzfrist-Umkehr (Rendite der letzten Wochen sagt die nächsten
  Wochen invers voraus) ist ein gut dokumentierter Effekt.
- **V1 (Gewicht senken) verworfen:** mildert nur den Schaden, bleibt negativ.
- **V3 (12-1-Momentum, Langfristig) verworfen:** im Training schlechter als die Basis, Out-of-Sample
  kein klarer Gewinn (Indizes unverändert negativ). Langfristig bleibt der Trend unverändert;
  der stark negative Langfrist-IC der Indizes 2020+ (n_eff nur 144) hat andere Ursachen
  (u. a. Makro) und ist offen. Forex und Rohstoffe (Trend zeigt dort keinen stabilen Effekt) sind unverändert.

**Ehrlicher Hinweis:** Die Wahl erfolgte am Trainingszeitraum; die Out-of-Sample-Periode 2020+ ist
nur eine einzige Marktphase (Corona-Crash, V-Erholung, 2022-Bärenmarkt) mit wenigen unabhängigen
Beobachtungen. Das Training und die Zeit vor 2020 wurden zudem schon im ersten Backtest gesehen
(Anlass der Überarbeitung). Die Basisrate steigender Kurse bleibt hoch: Auch der verbesserte Swing-Score ist
nur ein schwacher Hinweis (IC knapp 0,08), kein belastbares Handelssignal. Mit nur drei Varianten
und ohne Parametersuche ist das Overfitting-Risiko klein, aber nicht null; fortlaufend prüfen.

## Anhang: Prüfung des Langfrist-Profils (2026-11-21)

**Anlass:** Langfrist-IC negativ bei Indizes (−0,139) und Aktien (−0,059). **Ergebnis: keine Änderung.**
Skript: `backend/scripts/longterm_research.py` (gespeicherte Teilscores, Gewichte renormiert, Horizont 60 T).

**Diagnose (IC des Teilscores, Training 2013–2019 / OOS 2020+):** Indizes Makro −0,020 (t −0,2) / **−0,260 (t −3,2)**;
Indizes Trend −0,092 / −0,127; Indizes COT +0,061 / −0,112; Aktien Trend −0,020 / −0,029; Rohstoffe COT −0,142 / +0,068.
Im Training ist kein Faktor signifikant (alle |t| < 1,7); der Schaden entsteht fast nur in 2020+ (Indizes n_eff 144,
im Wesentlichen eine Marktphase: Corona-Erholung, Zinswende, 2022). Basisrate Indizes 69–72 % steigend.

| Klasse | Variante | IC Training (t) | IC OOS (t) |
|---|---|---|---|
| Indizes | Basis | -0,018 (-0,2) | -0,263 (-3,3) |
| Indizes | A Makro-Gewicht × 0,5 | -0,031 (-0,4) | -0,219 (-2,7) |
| Indizes | B Trend umgekehrt | +0,045 (+0,5) | -0,169 (-2,0) |
| Indizes | C Makro umgekehrt | +0,009 (+0,1) | +0,087 (+1,0) |
| Indizes | D Makro × 0,5 + Trend × 0,5 | -0,013 (-0,2) | -0,216 (-2,6) |
| Aktien | Basis | -0,029 (-0,7) | -0,085 (-2,1) |
| Aktien | B Trend umgekehrt | -0,002 (-0,1) | -0,058 (-1,4) |
| Aktien | D Makro × 0,5 + Trend × 0,5 | -0,033 (-0,8) | -0,090 (-2,2) |

**Entscheidung:** Keine Variante ist im Training klar besser (kein t über 0,5). Nur C (Makro umgekehrt) ist OOS positiv,
aber das wäre eine Auswahl auf dem OOS-Zeitraum, ökonomisch nicht begründbar (Wachstums-/Arbeitsmarktdaten
„besser“ → Index fällt?) und im Training wirkungslos: Overfitting-Verdacht. A/B/D mildern den Schaden nur. Nicht
getestet: Makro mit anderem Änderungsfenster (Neuberechnung nötig; Makro-IC im Training ≈ 0, daher kein Ansatz zur
Auswahl). **Langfrist-Scores für Indizes/Aktien haben derzeit keinen belegten Vorhersagewert.**

## Anhang: Crash-Dämpfung und Faktor-Übereinstimmung (2026-11-21)

**a) Crash-Dämpfung der Trend-Umkehr (Swing, Indizes/Aktien) – verworfen.** Idee: Nach extremen Kursstürzen ist die
Umkehr-Erwartung eher ein Regimewechsel als ein Rücksetzer; der Umkehr-Beitrag wird neutralisiert/abgeschwächt. Drei Varianten
(Skript `backend/scripts/crash_research.py`, gespeicherte Teilscores, nur Trend ersetzt, Gesamtscore renormiert; Horizont 10 T):
V1 ROC20 ≤ −35 % → Beitrag 0, V2 ROC20 ≤ −35 % → ×0,5, V3 ROC20 ≤ −25 % → 0.

| Klasse | Variante | IC Training (t) | IC OOS (t) | Stichtage ROC20 ≤ −35 % (Training / OOS) |
|---|---|---|---|---|
| Indizes | Basis (= V1, V2) | +0,074 (+2,2) | +0,081 (+2,4) | 0 / 0 |
| Indizes | V3 | +0,074 (+2,2) | +0,070 (+2,1) | 0 / 0 |
| Aktien | Basis | +0,077 (+4,6) | +0,022 (+1,3) | 0 / 17 |
| Aktien | V1 | +0,077 (+4,6) | +0,020 (+1,2) | 0 / 17 |
| Aktien | V2 | +0,077 (+4,6) | +0,021 (+1,3) | 0 / 17 |
| Aktien | V3 | +0,076 (+4,6) | +0,019 (+1,1) | 0 / 17 |

**Entscheidung: keine Änderung.** Im Training 2013–2019 gibt es bei wöchentlichen Stichtagen **keinen einzigen** Fall
(Aktien nur 12 mit ≤ −25 %), die Schwelle lässt sich dort nicht wählen. Nur OOS (17 Aktien-Stichtage, im Wesentlichen März 2020)
gibt es Fälle, und dort stiegen die Kurse nach dem Absturz im Mittel um **+5,4 % in 10 Tagen**: die Umkehr-Erwartung war richtig,
Dämpfen verschlechtert den IC leicht (+0,022 → +0,019…+0,021). Eine Dämpfung wäre also aus den Daten weder begründet noch
getestet; sie auf einen Einzelfall wie NVDA zu eichen wäre Overfitting. Stattdessen macht die UI das Signal sichtbar
(Marke „Gegentrend-Signal“, siehe b). Nicht geprüft: 40-Tage-Fenster (NVDA −45 % in 40 Tagen).

**b) Gegentrend-Kennzeichnung:** reine Anzeige, keine Score-Änderung (API `counter_trend` an der Trend-Zeile, wenn der
Umkehr-Modus aktiv ist und |Teilscore| ≥ Signalschwelle).

**c) Faktor-Übereinstimmung:** Anteil des Gewichts (renormiert) der Faktoren mit |Teilscore| ≥ 0,15, die in die Richtung des
Gesamtscores zeigen (`agreement` in der Scorecard). Zusatzauswertung der Richtungssignale: Übereinstimmung ≥ 70 % („hoch“)
gegen darunter (Tabelle im Kalibrierungs-Anhang). Ergebnis: **nur Swing-Aktien** zeigen einen Unterschied (hoch: Vorteil
+0,29 % je 10 T, t +2,3, Training +0,42 %, OOS +0,08 %; niedrig: ±0), bei Indizes ist die niedrige Gruppe nicht schlechter
als die hohe, bei Forex/Rohstoffe/Langfristig gibt es keinen Zusammenhang. Weil dafür 8 Gruppen getestet wurden, gilt für
„belegt“ ein strengeres t (2,7, Bonferroni, `agreement_min_t`); diese eine Gruppe erreicht es nicht → **schwach**. Fazit: Die
Übereinstimmung wird angezeigt, aber ausdrücklich als nicht belegt gekennzeichnet; sie erhöht die Trefferquote nicht belastbar.

<!-- calibration:start -->
## Anhang: Kalibrierung (Eichung der Score-Bereiche)

Erzeugt 2026-11-21 · Stichtage 2013-01-04 bis 2026-11-13 · Training bis 2019-12-31, Out-of-Sample danach · Datei `docs/calibration.json`, Befehl `uv run edgefinder calibrate`.

**Vorteil (`edge`)** = Ø Forward-Rendite der Signale in Signalrichtung minus Ø Rendite aller Beobachtungen der Klasse im gleichen Zeitraum. **Stufen:** *belegt* = Vorteil in Gesamt, Training und OOS positiv, t ≥ 2 (mit n_eff), n_eff ≥ 30 (je Zeitraum ≥ 10) und Trefferquote über der Basis; *schwach* = gleichsinnig, aber t oder Stichprobe zu klein; *kein Vorteil* = Vorzeichen wechselt, null oder falsch herum; *zu wenig Daten* = n_eff < 5 in einem Zeitraum. Die Rechnung ist ein Blick zurück, keine Prognose; Assets einer Klasse sind korreliert (t optimistisch).

### Richtungssignale je Profil und Klasse (bullish + bearish gepoolt, Kennwert-Horizont)

| Profil | Klasse | Horizont | Stufe | n_eff | Trefferquote | Basis-Treffer | Vorteil | t | Vorteil Training | Vorteil OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| Swing | Forex | 10 T | **kein Vorteil** | 1528 | 48,6 % | 50,1 % | -0,06 % | -1,3 | +0,01 % | -0,14 % |
| Swing | Indizes | 10 T | **schwach** | 457 | 47,3 % | 46,4 % | +0,24 % | +1,4 | +0,29 % | +0,18 % |
| Swing | Rohstoffe | 10 T | **kein Vorteil** | 762 | 48,9 % | 50,1 % | -0,07 % | -0,3 | -0,41 % | +0,26 % |
| Swing | Aktien | 10 T | **schwach** | 3164 | 52,0 % | 50,6 % | +0,21 % | +1,9 | +0,41 % | +0,04 % |
| Langfristig | Forex | 60 T | **kein Vorteil** | 264 | 51,7 % | 50,2 % | +0,04 % | +0,2 | +0,27 % | -0,25 % |
| Langfristig | Indizes | 60 T | **kein Vorteil** | 114 | 59,6 % | 62,1 % | -1,51 % | -2,3 | -0,23 % | -3,35 % |
| Langfristig | Rohstoffe | 60 T | **kein Vorteil** | 125 | 48,5 % | 50,1 % | -0,83 % | -0,7 | -1,67 % | -0,97 % |
| Langfristig | Aktien | 60 T | **kein Vorteil** | 764 | 64,6 % | 65,8 % | -0,65 % | -1,1 | -0,10 % | -1,14 % |

### Je Score-Bereich (Kennwert-Horizont)

| Profil | Klasse | Bereich | Stufe | n_eff | Treffer | Basis (steigend) | Ø Rendite | Vorteil | Vorteil Training | Vorteil OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| Swing | Forex | Stark bullish | zu wenig Daten | 6 | 66,7 % | 50,6 % | +0,68 % | +0,66 % | +0,69 % | – |
| Swing | Forex | Bullish | kein Vorteil | 914 | 50,5 % | 50,6 % | -0,02 % | -0,04 % | -0,01 % | -0,08 % |
| Swing | Forex | Neutral | neutral (keine Richtungsaussage) | 3526 | – | 50,6 % | +0,02 % | -0,01 % | +0,00 % | -0,02 % |
| Swing | Forex | Bearish | kein Vorteil | 606 | 45,6 % | 50,6 % | +0,12 % | -0,09 % | +0,01 % | -0,23 % |
| Swing | Forex | Stark bearish | zu wenig Daten | 2 | 75,0 % | 50,6 % | -1,02 % | +1,04 % | +1,01 % | – |
| Swing | Indizes | Stark bullish | zu wenig Daten | 0 | – | – | – | – | – | – |
| Swing | Indizes | Bullish | schwach | 152 | 65,0 % | 60,6 % | +1,17 % | +0,64 % | +0,63 % | +0,67 % |
| Swing | Indizes | Neutral | neutral (keine Richtungsaussage) | 1348 | – | 60,6 % | +0,46 % | -0,07 % | -0,06 % | -0,07 % |
| Swing | Indizes | Bearish | kein Vorteil | 306 | 38,5 % | 60,6 % | +0,50 % | +0,03 % | +0,10 % | -0,05 % |
| Swing | Indizes | Stark bearish | zu wenig Daten | 0 | – | – | – | – | – | – |
| Swing | Rohstoffe | Stark bullish | zu wenig Daten | 3 | 16,7 % | 52,5 % | +0,18 % | -0,05 % | +0,27 % | – |
| Swing | Rohstoffe | Bullish | kein Vorteil | 394 | 51,2 % | 52,5 % | +0,16 % | -0,07 % | -0,55 % | +0,32 % |
| Swing | Rohstoffe | Neutral | neutral (keine Richtungsaussage) | 682 | – | 52,5 % | +0,25 % | +0,01 % | +0,12 % | -0,11 % |
| Swing | Rohstoffe | Bearish | kein Vorteil | 361 | 46,9 % | 52,5 % | +0,27 % | -0,04 % | -0,27 % | +0,17 % |
| Swing | Rohstoffe | Stark bearish | zu wenig Daten | 4 | 14,3 % | 52,5 % | +2,07 % | -1,83 % | -2,15 % | – |
| Swing | Aktien | Stark bullish | zu wenig Daten | 18 | 61,1 % | 57,7 % | +0,47 % | -0,49 % | – | -0,46 % |
| Swing | Aktien | Bullish | schwach | 1683 | 59,7 % | 57,7 % | +1,23 % | +0,27 % | +0,69 % | +0,12 % |
| Swing | Aktien | Neutral | neutral (keine Richtungsaussage) | 4056 | – | 57,7 % | +0,90 % | -0,06 % | -0,01 % | -0,11 % |
| Swing | Aktien | Bearish | kein Vorteil | 1448 | 43,2 % | 57,7 % | +0,79 % | +0,17 % | +0,30 % | -0,20 % |
| Swing | Aktien | Stark bearish | zu wenig Daten | 16 | 34,4 % | 57,7 % | +2,23 % | -1,27 % | -1,04 % | -2,05 % |
| Langfristig | Forex | Stark bullish | zu wenig Daten | 2 | 63,3 % | 50,6 % | +2,23 % | +2,09 % | +2,37 % | – |
| Langfristig | Forex | Bullish | kein Vorteil | 176 | 51,8 % | 50,6 % | +0,18 % | +0,03 % | +0,33 % | -0,29 % |
| Langfristig | Forex | Neutral | neutral (keine Richtungsaussage) | 566 | – | 50,6 % | +0,12 % | -0,02 % | -0,16 % | +0,04 % |
| Langfristig | Forex | Bearish | kein Vorteil | 85 | 51,4 % | 50,6 % | +0,13 % | +0,01 % | +0,04 % | -0,18 % |
| Langfristig | Forex | Stark bearish | zu wenig Daten | 0 | 20,0 % | 50,6 % | +1,40 % | -1,26 % | -1,54 % | – |
| Langfristig | Indizes | Stark bullish | zu wenig Daten | 2 | 88,0 % | 70,6 % | +9,96 % | +6,74 % | +7,27 % | – |
| Langfristig | Indizes | Bullish | kein Vorteil | 88 | 69,8 % | 70,6 % | +2,06 % | -1,16 % | -0,19 % | -2,47 % |
| Langfristig | Indizes | Neutral | neutral (keine Richtungsaussage) | 183 | – | 70,6 % | +3,24 % | +0,02 % | -0,31 % | +0,15 % |
| Langfristig | Indizes | Bearish | kein Vorteil | 24 | 19,1 % | 70,6 % | +6,76 % | -3,54 % | -1,60 % | -5,98 % |
| Langfristig | Indizes | Stark bearish | zu wenig Daten | 0 | – | – | – | – | – | – |
| Langfristig | Rohstoffe | Stark bullish | zu wenig Daten | 0 | 0,0 % | 53,6 % | -12,21 % | -14,26 % | -11,49 % | – |
| Langfristig | Rohstoffe | Bullish | kein Vorteil | 65 | 56,1 % | 53,6 % | +1,71 % | -0,34 % | -0,63 % | -0,87 % |
| Langfristig | Rohstoffe | Neutral | neutral (keine Richtungsaussage) | 112 | – | 53,6 % | +1,58 % | -0,47 % | -1,23 % | +0,11 % |
| Langfristig | Rohstoffe | Bearish | kein Vorteil | 58 | 41,0 % | 53,6 % | +3,32 % | -1,27 % | -2,23 % | -1,12 % |
| Langfristig | Rohstoffe | Stark bearish | zu wenig Daten | 2 | 29,6 % | 53,6 % | +4,21 % | -2,16 % | -4,93 % | – |
| Langfristig | Aktien | Stark bullish | kein Vorteil | 76 | 62,9 % | 67,0 % | +6,15 % | +0,17 % | +1,19 % | -0,55 % |
| Langfristig | Aktien | Bullish | kein Vorteil | 661 | 66,2 % | 67,0 % | +5,43 % | -0,55 % | -0,19 % | -0,88 % |
| Langfristig | Aktien | Neutral | neutral (keine Richtungsaussage) | 421 | – | 67,0 % | +6,46 % | +0,48 % | +0,03 % | +1,06 % |
| Langfristig | Aktien | Bearish | kein Vorteil | 27 | 29,6 % | 67,0 % | +11,32 % | -5,34 % | -1,07 % | -9,94 % |
| Langfristig | Aktien | Stark bearish | zu wenig Daten | 0 | – | – | – | – | – | – |

### Faktor-Übereinstimmung ≥ 70 % (Richtungssignale, Kennwert-Horizont)

| Profil | Klasse | Gruppe | Stufe | n_eff | Trefferquote | Vorteil | Vorteil Training | Vorteil OOS |
|---|---|---|---|---|---|---|---|---|
| Swing | Forex | hoch | kein Vorteil | 716 | 50,4 % | +0,02 % | +0,11 % | -0,12 % |
| Swing | Forex | niedrig | kein Vorteil | 812 | 47,0 % | -0,13 % | -0,09 % | -0,16 % |
| Swing | Indizes | hoch | schwach | 212 | 46,2 % | +0,20 % | +0,23 % | +0,13 % |
| Swing | Indizes | niedrig | schwach | 245 | 48,2 % | +0,27 % | +0,35 % | +0,20 % |
| Swing | Rohstoffe | hoch | kein Vorteil | 514 | 48,6 % | +0,05 % | -0,28 % | +0,38 % |
| Swing | Rohstoffe | niedrig | kein Vorteil | 248 | 49,4 % | -0,31 % | -0,71 % | +0,03 % |
| Swing | Aktien | hoch | schwach | 2323 | 50,8 % | +0,29 % | +0,41 % | +0,07 % |
| Swing | Aktien | niedrig | kein Vorteil | 842 | 55,3 % | -0,01 % | +0,15 % | -0,00 % |
| Langfristig | Forex | hoch | kein Vorteil | 138 | 53,1 % | +0,10 % | +0,43 % | -0,53 % |
| Langfristig | Forex | niedrig | kein Vorteil | 127 | 50,3 % | -0,02 % | +0,05 % | -0,04 % |
| Langfristig | Indizes | hoch | kein Vorteil | 59 | 65,0 % | -1,46 % | -0,09 % | -4,83 % |
| Langfristig | Indizes | niedrig | kein Vorteil | 55 | 53,8 % | -1,56 % | -0,48 % | -2,61 % |
| Langfristig | Rohstoffe | hoch | kein Vorteil | 58 | 42,9 % | -1,65 % | -2,45 % | -1,80 % |
| Langfristig | Rohstoffe | niedrig | kein Vorteil | 67 | 53,4 % | -0,12 % | -0,78 % | -0,45 % |
| Langfristig | Aktien | hoch | kein Vorteil | 629 | 65,0 % | -0,45 % | -0,04 % | -1,00 % |
| Langfristig | Aktien | niedrig | kein Vorteil | 136 | 62,6 % | -1,56 % | -2,08 % | -1,45 % |

<!-- calibration:end -->
