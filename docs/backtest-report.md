# Backtest-Report

Erzeugt: 2026-11-18T15:18:57+00:00 · Zeitraum der Stichtage: 2013-01-04 bis 2026-11-18 · 730 Stichtage, 62771 Scores (je Asset und Profil) · Handelstage-Abstand der Stichtage ≈ 5.

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
| Swing | Forex | 10 T | 10.108 | 2944 | 49,2 % | 50,6 % | -0,15 % | -0,025 | -1,8 | -0,012 |
| Swing | Indizes | 10 T | 3.610 | 1228 | 54,5 % | 60,6 % | -1,18 % | -0,088 | -3,8 * | +0,013 |
| Swing | Rohstoffe | 10 T | 2.888 | 1133 | 50,1 % | 52,5 % | +0,18 % | -0,010 | -0,4 | – |
| Swing | Aktien | 10 T | 14.440 | 7263 | 53,7 % | 57,7 % | -1,20 % | -0,053 | -4,5 * | -0,010 |
| Swing | Alle Klassen | 10 T | 31.046 | 12568 | 52,4 % | 55,2 % | -0,73 % | -0,044 | -5,5 * | +0,017 |
| Langfristig | Forex | 60 T | 9.968 | 3349 | 49,9 % | 50,6 % | -0,32 % | -0,020 | -0,6 | -0,005 |
| Langfristig | Indizes | 60 T | 3.559 | 1317 | 62,0 % | 70,6 % | -5,03 % | -0,153 | -2,7 * | +0,017 |
| Langfristig | Rohstoffe | 60 T | 2.848 | 1191 | 48,3 % | 53,6 % | -2,21 % | -0,009 | -0,1 | – |
| Langfristig | Aktien | 60 T | 14.231 | 9174 | 64,6 % | 67,0 % | -5,82 % | -0,059 | -2,0 * | -0,001 |
| Langfristig | Alle Klassen | 60 T | 30.606 | 15031 | 59,8 % | 60,8 % | -3,60 % | -0,053 | -2,7 * | +0,080 |

## Details je Profil, Klasse und Horizont

### Swing · Forex

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 10.136 | 10.136 | 49,1 % (n=2956) | 50,2 % | +0,01 % | -0,04 % | -1,0 | -0,020 | -2,1 * | -0,016 |
| 10 T (Kennwert) | 10.108 | 5.054 | 49,2 % (n=2944) | 50,6 % | +0,03 % | -0,15 % | -1,7 | -0,025 | -1,8 | -0,012 |
| 20 T | 10.080 | 2.520 | 46,5 % (n=2934) | 50,5 % | +0,05 % | -0,35 % | -2,0 | -0,051 | -2,6 * | -0,039 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 23 ⚠ | 73,9 % | 73,9 % | +1,16 % | +1,41 % |
| Bullish (+2 bis +6) | 1717 | 50,3 % | 50,3 % | -0,02 % | +0,01 % |
| Neutral (-2 bis +2) | 7164 | (neutral) | 50,3 % | +0,01 % | +0,01 % |
| Bearish (-6 bis -2) | 1200 | 47,1 % | 52,8 % | +0,15 % | +0,08 % |
| Stark bearish (-10 bis -6) | 4 ⚠ | 50,0 % | 50,0 % | -0,05 % | +0,00 % |

### Swing · Indizes

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 3.619 | 3.619 | 53,5 % (n=1229) | 57,2 % | +0,27 % | -0,72 % | -2,7 * | -0,049 | -3,0 * | +0,023 |
| 10 T (Kennwert) | 3.610 | 1.805 | 54,5 % (n=1228) | 60,6 % | +0,53 % | -1,18 % | -2,1 * | -0,088 | -3,8 * | +0,013 |
| 20 T | 3.600 | 900 | 55,6 % (n=1228) | 64,1 % | +1,07 % | -2,95 % | -3,2 * | -0,123 | -3,7 * | +0,008 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 8 ⚠ | 75,0 % | 75,0 % | -1,02 % | +0,63 % |
| Bullish (+2 bis +6) | 980 | 59,7 % | 59,7 % | +0,40 % | +0,50 % |
| Neutral (-2 bis +2) | 2382 | (neutral) | 60,2 % | +0,49 % | +0,74 % |
| Bearish (-6 bis -2) | 240 | 32,5 % | 67,5 % | +1,56 % | +2,28 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Swing · Rohstoffe

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 2.896 | 2.896 | 50,1 % (n=1141) | 52,3 % | +0,15 % | +0,11 % | +0,4 | -0,003 | -0,1 | – |
| 10 T (Kennwert) | 2.888 | 1.444 | 50,1 % (n=1133) | 52,5 % | +0,24 % | +0,18 % | +0,3 | -0,010 | -0,4 | – |
| 20 T | 2.880 | 720 | 50,1 % (n=1130) | 51,6 % | +0,49 % | +1,25 % | +0,9 | -0,007 | -0,2 | – |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 0 ⚠ | – | – | – | – |
| Bullish (+2 bis +6) | 571 | 53,8 % | 53,8 % | +0,36 % | +0,22 % |
| Neutral (-2 bis +2) | 1755 | (neutral) | 51,7 % | +0,21 % | +0,17 % |
| Bearish (-6 bis -2) | 562 | 46,4 % | 53,4 % | +0,18 % | +0,27 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Swing · Aktien

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 14.480 | 14.480 | 53,3 % (n=7289) | 55,7 % | +0,48 % | -0,69 % | -3,8 * | -0,037 | -4,4 * | -0,003 |
| 10 T (Kennwert) | 14.440 | 7.220 | 53,7 % (n=7263) | 57,7 % | +0,96 % | -1,20 % | -3,5 * | -0,053 | -4,5 * | -0,010 |
| 20 T | 14.400 | 3.600 | 55,5 % (n=7237) | 60,4 % | +1,95 % | -1,75 % | -2,5 * | -0,064 | -3,9 * | -0,007 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 171 | 52,0 % | 52,0 % | +1,02 % | +0,15 % |
| Bullish (+2 bis +6) | 6049 | 56,6 % | 56,6 % | +0,77 % | +0,66 % |
| Neutral (-2 bis +2) | 7177 | (neutral) | 57,9 % | +0,97 % | +0,91 % |
| Bearish (-6 bis -2) | 1043 | 36,7 % | 63,3 % | +1,98 % | +1,62 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Swing · Alle Klassen

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 T | 31.131 | 31.131 | 52,0 % (n=12615) | 53,8 % | +0,27 % | -0,41 % | – | -0,030 | -5,2 * | +0,013 |
| 10 T (Kennwert) | 31.046 | 15.523 | 52,4 % (n=12568) | 55,2 % | +0,54 % | -0,73 % | – | -0,044 | -5,5 * | +0,017 |
| 20 T | 30.960 | 7.740 | 52,9 % (n=12529) | 56,8 % | +1,09 % | -1,15 % | – | -0,061 | -5,4 * | +0,024 |

Score-Bereiche, Horizont 10 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 202 | 55,4 % | 55,4 % | +0,96 % | +0,32 % |
| Bullish (+2 bis +6) | 9317 | 55,6 % | 55,6 % | +0,56 % | +0,38 % |
| Neutral (-2 bis +2) | 18478 | (neutral) | 54,7 % | +0,46 % | +0,29 % |
| Bearish (-6 bis -2) | 3045 | 42,3 % | 57,6 % | +0,89 % | +0,46 % |
| Stark bearish (-10 bis -6) | 4 ⚠ | 50,0 % | 50,0 % | -0,05 % | +0,00 % |

### Langfristig · Forex

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 10.080 | 2.520 | 48,5 % (n=3376) | 50,5 % | +0,05 % | -0,24 % | -1,5 | -0,013 | -0,6 | -0,001 |
| 60 T (Kennwert) | 9.968 | 831 | 49,9 % (n=3349) | 50,6 % | +0,14 % | -0,32 % | -0,7 | -0,020 | -0,6 | -0,005 |
| 120 T | 9.800 | 408 | 49,8 % (n=3266) | 50,6 % | +0,26 % | -0,05 % | -0,0 | +0,006 | +0,1 | +0,006 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 77 | 66,2 % | 66,2 % | +1,25 % | +1,76 % |
| Bullish (+2 bis +6) | 2240 | 47,3 % | 47,3 % | -0,30 % | -0,23 % |
| Neutral (-2 bis +2) | 6619 | (neutral) | 52,3 % | +0,29 % | +0,20 % |
| Bearish (-6 bis -2) | 1025 | 54,3 % | 45,6 % | +0,06 % | -0,35 % |
| Stark bearish (-10 bis -6) | 7 ⚠ | 42,9 % | 57,1 % | +0,93 % | +0,71 % |

### Langfristig · Indizes

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 3.600 | 900 | 57,9 % (n=1333) | 64,1 % | +1,07 % | -2,46 % | -3,0 * | -0,096 | -2,9 * | +0,050 |
| 60 T (Kennwert) | 3.559 | 297 | 62,0 % (n=1317) | 70,6 % | +3,22 % | -5,03 % | -2,2 * | -0,153 | -2,7 * | +0,017 |
| 120 T | 3.495 | 146 | 61,5 % (n=1296) | 75,5 % | +6,43 % | -9,20 % | -2,4 * | -0,177 | -2,2 * | -0,032 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 45 | 86,7 % | 86,7 % | +4,59 % | +4,89 % |
| Bullish (+2 bis +6) | 1063 | 68,9 % | 68,9 % | +2,03 % | +2,68 % |
| Neutral (-2 bis +2) | 2242 | (neutral) | 70,4 % | +3,39 % | +3,77 % |
| Bearish (-6 bis -2) | 209 | 22,0 % | 78,0 % | +7,16 % | +6,80 % |
| Stark bearish (-10 bis -6) | 0 ⚠ | – | – | – | – |

### Langfristig · Rohstoffe

| Horizont | n | n_eff | Trefferquote | Basis steigend | Ø Rendite gesamt | Spread | t(Spread) | IC | t(IC) | IC (Querschn.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 T | 2.880 | 720 | 48,2 % (n=1202) | 51,6 % | +0,49 % | -0,50 % | -0,5 | -0,019 | -0,5 | – |
| 60 T (Kennwert) | 2.848 | 237 | 48,3 % (n=1191) | 53,6 % | +2,05 % | -2,21 % | -0,8 | -0,009 | -0,1 | – |
| 120 T | 2.796 | 116 | 50,8 % (n=1169) | 54,7 % | +3,95 % | +1,28 % | +0,2 | +0,050 | +0,5 | – |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 0 ⚠ | – | – | – | – |
| Bullish (+2 bis +6) | 607 | 54,7 % | 54,7 % | +1,36 % | +1,16 % |
| Neutral (-2 bis +2) | 1657 | (neutral) | 51,5 % | +1,77 % | +0,42 % |
| Bearish (-6 bis -2) | 570 | 42,6 % | 57,4 % | +3,44 % | +2,09 % |
| Stark bearish (-10 bis -6) | 14 ⚠ | 0,0 % | 100,0 % | +8,81 % | +9,24 % |

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
| 20 T | 30.951 | 7.738 | 55,5 % (n=15196) | 56,8 % | +1,09 % | -1,19 % | – | -0,037 | -3,3 * | +0,056 |
| 60 T (Kennwert) | 30.606 | 2.550 | 59,8 % (n=15031) | 60,8 % | +3,39 % | -3,60 % | – | -0,053 | -2,7 * | +0,080 |
| 120 T | 30.062 | 1.253 | 63,3 % (n=14776) | 64,1 % | +6,93 % | -6,80 % | – | -0,033 | -1,2 | +0,124 |

Score-Bereiche, Horizont 60 Handelstage:

| Bereich | n | Trefferquote | Anteil steigend | Ø Rendite | Median |
|---|---|---|---|---|---|
| Stark bullish (+6 bis +10) | 1031 | 64,2 % | 64,2 % | +5,71 % | +3,57 % |
| Bullish (+2 bis +6) | 11847 | 62,3 % | 62,3 % | +3,83 % | +2,33 % |
| Neutral (-2 bis +2) | 15575 | (neutral) | 60,2 % | +2,90 % | +1,38 % |
| Bearish (-6 bis -2) | 2132 | 44,2 % | 55,7 % | +3,39 % | +0,78 % |
| Stark bearish (-10 bis -6) | 21 ⚠ | 14,3 % | 85,7 % | +6,18 % | +4,61 % |

## Faktoren (IC je Teilscore, Kennwert-Horizont)

Hinweis für Tuning-Kandidaten, keine Gewichtsänderung ohne Jonas. IC nur über Stichtage, an denen der Faktor verfügbar war.

### Swing (Horizont 10 T)

| Klasse | Faktor | Gewicht | Verfügbar | n | IC | t |
|---|---|---|---|---|---|---|
| Forex | COT | 25 % | 37 % | 3640 | -0,081 | -3,5 * |
| Forex | Retail-Sentiment | 20 % | 0 % | 0 | – | – |
| Forex | Makro | 15 % | 94 % | 9521 | +0,010 | +0,7 |
| Forex | Trend | 30 % | 100 % | 10108 | -0,032 | -2,3 * |
| Forex | Saisonalität | 10 % | 87 % | 8736 | +0,029 | +1,9 |
| Indizes | COT | 20 % | 29 % | 1040 | +0,053 | +1,2 |
| Indizes | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Indizes | Makro | 15 % | 96 % | 3460 | -0,026 | -1,1 |
| Indizes | Trend | 35 % | 100 % | 3610 | -0,120 | -5,1 * |
| Indizes | Saisonalität | 10 % | 87 % | 3120 | +0,016 | +0,6 |
| Indizes | AAII | 15 % | 1 % | 10 | -0,453 | -0,9 |
| Rohstoffe | COT | 30 % | 37 % | 1040 | +0,018 | +0,4 |
| Rohstoffe | Retail-Sentiment | 15 % | 0 % | 0 | – | – |
| Rohstoffe | Makro | 10 % | 100 % | 2888 | -0,043 | -1,6 |
| Rohstoffe | Trend | 35 % | 100 % | 2888 | -0,014 | -0,5 |
| Rohstoffe | Saisonalität | 10 % | 87 % | 2496 | -0,003 | -0,1 |
| Aktien | Fundamentals | 15 % | 0 % | 0 | – | – |
| Aktien | Earnings | 20 % | 43 % | 6051 | +0,003 | +0,2 |
| Aktien | Trend | 30 % | 100 % | 14440 | -0,057 | -4,8 * |
| Aktien | Short Interest | 10 % | 14 % | 1840 | +0,010 | +0,3 |
| Aktien | Insider | 10 % | 0 % | 0 | – | – |
| Aktien | Saisonalität | 5 % | 86 % | 12454 | +0,017 | +1,4 |
| Aktien | AAII | 10 % | 1 % | 40 | -0,243 | -1,1 |

### Langfristig (Horizont 60 T)

| Klasse | Faktor | Gewicht | Verfügbar | n | IC | t |
|---|---|---|---|---|---|---|
| Forex | COT | 25 % | 37 % | 3500 | -0,101 | -1,7 |
| Forex | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Forex | Makro | 40 % | 93 % | 9295 | -0,005 | -0,1 |
| Forex | Trend | 20 % | 100 % | 9968 | +0,007 | +0,2 |
| Forex | Saisonalität | 10 % | 87 % | 8596 | -0,021 | -0,6 |
| Indizes | COT | 15 % | 29 % | 999 | -0,036 | -0,3 |
| Indizes | Retail-Sentiment | 5 % | 0 % | 0 | – | – |
| Indizes | Makro | 35 % | 93 % | 3303 | -0,153 | -2,6 * |
| Indizes | Trend | 25 % | 100 % | 3559 | -0,108 | -1,9 |
| Indizes | Saisonalität | 10 % | 87 % | 3069 | +0,021 | +0,3 |
| Indizes | AAII | 10 % | 1 % | 0 | – | – |
| Rohstoffe | COT | 30 % | 37 % | 1000 | +0,055 | +0,5 |
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
| Aktien | AAII | 10 % | 1 % | 0 | – | – |

## Stabilität nach Jahr (IC, Kennwert-Horizont)

Zelle: IC (Anzahl Beobachtungen). Jahre mit weniger Beobachtungen als die Schwelle sind mit ⚠ markiert.

### Swing (Horizont 10 T)

| Klasse | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Forex | +0,02 (728) | +0,06 (728) | -0,02 (728) | +0,02 (742) | -0,07 (728) | +0,00 (728) | -0,01 (728) | -0,01 (728) | -0,10 (742) | +0,07 (728) | -0,16 (728) | -0,13 (728) | -0,09 (728) | -0,07 (616) |
| Indizes | -0,15 (260) | -0,35 (260) | +0,01 (260) | -0,06 (265) | -0,02 (260) | -0,11 (260) | -0,27 (260) | -0,20 (260) | -0,17 (265) | -0,12 (260) | +0,05 (260) | -0,21 (260) | -0,05 (260) | +0,01 (220) |
| Rohstoffe | -0,10 (208) | +0,04 (208) | -0,10 (208) | -0,17 (212) | -0,28 (208) | -0,06 (208) | +0,09 (208) | -0,06 (208) | -0,12 (212) | -0,06 (208) | -0,25 (208) | -0,01 (208) | +0,13 (208) | +0,01 (176) |
| Aktien | -0,10 (1040) | -0,12 (1040) | -0,04 (1040) | -0,08 (1060) | -0,17 (1040) | -0,05 (1040) | -0,08 (1040) | -0,09 (1040) | -0,11 (1060) | -0,06 (1040) | -0,10 (1040) | -0,01 (1040) | +0,03 (1040) | +0,00 (880) |
| Alle Klassen | -0,02 (2236) | -0,05 (2236) | -0,01 (2236) | -0,04 (2279) | -0,07 (2236) | -0,01 (2236) | +0,01 (2236) | -0,04 (2236) | -0,00 (2279) | -0,04 (2236) | -0,05 (2236) | -0,00 (2236) | +0,05 (2236) | +0,00 (1892) |

### Langfristig (Horizont 60 T)

| Klasse | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Forex | +0,18 (728) | +0,11 (728) | -0,10 (728) | +0,04 (742) | -0,19 (728) | -0,25 (728) | -0,28 (728) | +0,01 (728) | +0,17 (742) | +0,12 (728) | -0,09 (728) | -0,23 (728) | -0,35 (728) | +0,32 (476) |
| Indizes | -0,06 (260) | -0,29 (260) | +0,01 (260) | +0,12 (265) | -0,21 (260) | -0,29 (260) | -0,26 (260) | -0,45 (260) | -0,13 (265) | -0,35 (260) | -0,16 (260) | -0,22 (260) | -0,19 (260) | -0,14 (169) |
| Rohstoffe | -0,07 (208) | -0,50 (208) | +0,06 (208) | -0,44 (212) | -0,02 (208) | -0,26 (208) | +0,14 (208) | -0,37 (208) | -0,23 (212) | -0,29 (208) | -0,36 (208) | -0,19 (208) | +0,35 (208) | -0,09 (136) |
| Aktien | +0,00 (1031) | -0,02 (1040) | -0,05 (1040) | -0,13 (1060) | +0,13 (1040) | -0,19 (1040) | -0,14 (1040) | -0,20 (1040) | -0,17 (1060) | -0,19 (1040) | -0,12 (1040) | -0,06 (1040) | -0,04 (1040) | +0,01 (680) |
| Alle Klassen | +0,18 (2227) | +0,11 (2236) | +0,03 (2236) | -0,07 (2279) | +0,23 (2236) | -0,09 (2236) | +0,01 (2236) | -0,05 (2236) | +0,12 (2279) | -0,14 (2236) | +0,05 (2236) | +0,10 (2236) | -0,01 (2236) | +0,07 (1461) |

## Abdeckung je Zeitraum

Anteil der Scores (Profil Swing), in denen der Faktor einen Wert lieferte; Gewichte fehlender Faktoren werden renormiert. Retail-Sentiment, AAII und Short Interest haben keine bzw. kaum Historie vor 2024-11, COT reicht 6 Jahre zurück.

### Forex

| Jahr | Scores | Ø Abdeckung | COT | Makro | Retail-Sentiment | Saisonalität | Trend |
|---|---|---|---|---|---|---|---|
| 2013 | 728 | 39 % | 0 % | 61 % | 0 % | 0 % | 100 % |
| 2014 | 728 | 40 % | 0 % | 59 % | 0 % | 12 % | 100 % |
| 2015 | 728 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2016 | 742 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2017 | 728 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2018 | 728 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2019 | 728 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2020 | 728 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2021 | 742 | 59 % | 15 % | 100 % | 0 % | 100 % | 100 % |
| 2022 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2023 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2024 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2025 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2026 | 728 | 80 % | 100 % | 100 % | 0 % | 100 % | 100 % |

### Indizes

| Jahr | Scores | Ø Abdeckung | AAII | COT | Makro | Retail-Sentiment | Saisonalität | Trend |
|---|---|---|---|---|---|---|---|---|
| 2013 | 260 | 44 % | 0 % | 0 % | 60 % | 0 % | 0 % | 100 % |
| 2014 | 260 | 48 % | 0 % | 0 % | 82 % | 0 % | 12 % | 100 % |
| 2015 | 260 | 60 % | 0 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2016 | 265 | 60 % | 0 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2017 | 260 | 60 % | 0 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2018 | 260 | 60 % | 0 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2019 | 260 | 60 % | 0 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2020 | 260 | 60 % | 0 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2021 | 265 | 62 % | 0 % | 12 % | 100 % | 0 % | 100 % | 100 % |
| 2022 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2023 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2024 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2025 | 260 | 76 % | 0 % | 80 % | 100 % | 0 % | 100 % | 100 % |
| 2026 | 260 | 79 % | 19 % | 80 % | 100 % | 0 % | 100 % | 100 % |

### Rohstoffe

| Jahr | Scores | Ø Abdeckung | COT | Makro | Retail-Sentiment | Saisonalität | Trend |
|---|---|---|---|---|---|---|---|
| 2013 | 208 | 45 % | 0 % | 100 % | 0 % | 0 % | 100 % |
| 2014 | 208 | 46 % | 0 % | 100 % | 0 % | 12 % | 100 % |
| 2015 | 208 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2016 | 212 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2017 | 208 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2018 | 208 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2019 | 208 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2020 | 208 | 55 % | 0 % | 100 % | 0 % | 100 % | 100 % |
| 2021 | 212 | 60 % | 15 % | 100 % | 0 % | 100 % | 100 % |
| 2022 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2023 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2024 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2025 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |
| 2026 | 208 | 85 % | 100 % | 100 % | 0 % | 100 % | 100 % |

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
| 2026 | 1040 | 67 % | 19 % | 100 % | 0 % | 0 % | 100 % | 100 % | 100 % |
