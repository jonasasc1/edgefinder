# ruff: noqa: E501  (lange deutsche Fließtexte im Report)
"""Markdown-Report und JSON des Backtests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from edgefinder.scoring.factors import de

CLASS_NAME = {
    "forex": "Forex",
    "index": "Indizes",
    "commodity": "Rohstoffe",
    "stock": "Aktien",
    "all": "Alle Klassen",
}
FACTOR_NAME = {
    "cot": "COT",
    "retail_sentiment": "Retail-Sentiment",
    "macro": "Makro",
    "trend": "Trend",
    "seasonality": "Saisonalität",
    "aaii": "AAII",
    "fundamentals": "Fundamentals",
    "earnings": "Earnings",
    "short_interest": "Short Interest",
    "insider": "Insider",
}


def _pct(value: float | None, digits: int = 1, signed: bool = False) -> str:
    if value is None:
        return "–"
    return de(value * 100, ("+" if signed else "") + f".{digits}f") + " %"


def _num(value: float | None, spec: str = "+.3f") -> str:
    return "–" if value is None else de(value, spec)


def _flag(enough: bool) -> str:
    return "" if enough else " ⚠"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return [*lines, ""]


def _significance(t: float | None) -> str:
    if t is None:
        return "–"
    mark = " *" if abs(t) >= 2 else ""
    return de(t, "+.1f") + mark


LONGTERM_APPENDIX = """\
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
"""


TREND_APPENDIX = """\
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
"""


def render_markdown(result: dict[str, Any]) -> str:
    primary = result["primary_horizon"]
    lines = [
        "# Backtest-Report",
        "",
        f"Erzeugt: {result['generated_at']} · Zeitraum der Stichtage: {result['first_date']} bis "
        f"{result['last_date']} · {result['dates']} Stichtage, {result['scores']} Scores "
        f"(je Asset und Profil) · Handelstage-Abstand der Stichtage ≈ {result['step_trading_days']}.",
        "",
        "## Methode und Lesehilfe",
        "",
        "- Jeder gespeicherte Score wird mit der Rendite vom letzten Schlusskurs ≤ Stichtag bis `h` "
        "Handelstage später verglichen. Der Score kennt nur Daten bis zum Stichtag (Look-Ahead-Schutz "
        "der Score-Engine); Renditefenster über den letzten Kurs hinaus entfallen.",
        "- **Trefferquote:** Anteil der Signale mit korrekter Richtung. Signal = Score in einem "
        "bullishen bzw. bearishen Bereich (`scoring.labels`, ohne „Neutral“). **Basis (steigend)** "
        "ist der Anteil positiver Forward-Renditen über alle Beobachtungen: Indizes und Aktien "
        "steigen im Zeitraum überwiegend, eine Trefferquote bullisher Signale ist nur im Vergleich "
        "dazu aussagekräftig.",
        "- **Spread:** mittlere Forward-Rendite aller bullishen minus aller bearishen Signale.",
        "- **IC:** Spearman-Rangkorrelation Score ↔ Forward-Rendite (gepoolt über alle Assets und "
        "Stichtage); **IC (Querschnitt)** = Mittel der IC je Stichtag über die Assets einer Klasse "
        "(nur Tage mit ≥ 5 Assets).",
        "- **t-Werte** sind mit der effektiven Stichprobengröße `n / (h / Abstand)` gerechnet; ein "
        "Stern kennzeichnet |t| ≥ 2.",
        "- **Alle Klassen:** IC und Spread sind das n-gewichtete Mittel der Klassenwerte (gepoolt würden unterschiedliche Basisrenditen der Klassen sie verfälschen); Trefferquote und Bereiche sind gepoolt.",
        f"- ⚠ = weniger als {result['min_signals']} Beobachtungen: nicht belastbar.",
        "",
        "> **Überlappung/Autokorrelation:** Bei wöchentlichen Stichtagen überlappen sich "
        "Renditefenster ab einem Horizont über 5 Handelstagen (z. B. 60 Tage: ca. 12 Stichtage "
        "teilen sich Kurse). Die Beobachtungen sind nicht unabhängig; n überzeichnet die "
        "Aussagekraft, deshalb zusätzlich n_eff. Zudem sind Assets innerhalb einer Klasse stark "
        "korreliert (z. B. alle USD-Paare an einem Tag) – die t-Werte bleiben daher optimistisch. "
        "Die Gewichte/Parameter sind nicht am Backtest optimiert, trotzdem wurden Schwellen und "
        "Faktoren vor der Auswertung gewählt; mehrere Vergleiche (Profile × Klassen × Horizonte) "
        "erzeugen einzelne Zufallstreffer.",
        "",
    ]
    groups = result["groups"]

    lines += ["## Überblick (Kennwert-Horizont je Profil)", ""]
    rows = []
    for g in groups:
        if not g["primary"]:
            continue
        d = g["directional"]
        rows.append(
            [
                result["profiles"][g["profile"]],
                CLASS_NAME[g["asset_class"]],
                f"{g['horizon']} T",
                f"{de(g['n'], '.0f')}{_flag(g['enough'])}",
                f"{d['n']}",
                _pct(d["hit_rate"], 1) + _flag(d["enough"]),
                _pct(g["base_up"], 1),
                _pct(g["spread"], 2, True),
                _num(g["ic"]),
                _significance(g["ic_t"]),
                _num(g["ic_cs"]),
            ]
        )
    lines += _table(
        ["Profil", "Klasse", "Horizont", "n", "Signale", "Trefferquote", "Basis steigend",
         "Spread", "IC", "t(IC)", "IC (Querschn.)"],
        rows,
    )  # fmt: skip

    lines += ["## Details je Profil, Klasse und Horizont", ""]
    for profile, label in result["profiles"].items():
        for asset_class in [*result["classes"], "all"]:
            block = [
                g for g in groups if g["profile"] == profile and g["asset_class"] == asset_class
            ]
            if not block:
                continue
            lines += [f"### {label} · {CLASS_NAME[asset_class]}", ""]
            summary = []
            for g in block:
                d = g["directional"]
                summary.append(
                    [
                        f"{g['horizon']} T" + (" (Kennwert)" if g["primary"] else ""),
                        f"{de(g['n'], '.0f')}{_flag(g['enough'])}",
                        de(g["n_eff"], ".0f"),
                        _pct(d["hit_rate"], 1) + f" (n={d['n']})",
                        _pct(g["base_up"], 1),
                        _pct(g["base_mean"], 2, True),
                        _pct(g["spread"], 2, True),
                        _significance(g["spread_t"]),
                        _num(g["ic"]),
                        _significance(g["ic_t"]),
                        _num(g["ic_cs"]),
                    ]
                )
            lines += _table(
                ["Horizont", "n", "n_eff", "Trefferquote", "Basis steigend", "Ø Rendite gesamt",
                 "Spread", "t(Spread)", "IC", "t(IC)", "IC (Querschn.)"],
                summary,
            )  # fmt: skip
            main = next((g for g in block if g["primary"]), block[0])
            lines += [f"Score-Bereiche, Horizont {main['horizon']} Handelstage:", ""]
            rows = []
            for b in main["buckets"]:
                rows.append(
                    [
                        f"{b['label']} ({de(b['low'], '+.0f')} bis {de(b['high'], '+.0f')})",
                        f"{b['n']}{_flag(b['enough'])}",
                        _pct(b["hit_rate"], 1) if b["direction"] else "(neutral)",
                        _pct(b["up_share"], 1),
                        _pct(b["mean"], 2, True),
                        _pct(b["median"], 2, True),
                    ]
                )
            lines += _table(
                ["Bereich", "n", "Trefferquote", "Anteil steigend", "Ø Rendite", "Median"], rows
            )

    lines += ["## Faktoren (IC je Teilscore, Kennwert-Horizont)", "",
              "Hinweis für Tuning-Kandidaten, keine Gewichtsänderung ohne Jonas. IC nur über "
              "Stichtage, an denen der Faktor verfügbar war.", ""]  # fmt: skip
    for profile, label in result["profiles"].items():
        rows = []
        for f in result["factors"]:
            if f["profile"] != profile:
                continue
            rows.append(
                [
                    CLASS_NAME[f["asset_class"]],
                    FACTOR_NAME.get(f["factor"], f["factor"]),
                    de(f["weight"] * 100, ".0f") + " %",
                    _pct(f["availability"], 0),
                    f"{f['n']}",
                    _num(f["ic"]),
                    _significance(f["ic_t"]),
                ]
            )
        lines += [f"### {label} (Horizont {primary[profile]} T)", ""]
        lines += _table(["Klasse", "Faktor", "Gewicht", "Verfügbar", "n", "IC", "t"], rows)

    lines += ["## Stabilität nach Jahr (IC, Kennwert-Horizont)", "",
              "Zelle: IC (Anzahl Beobachtungen). Jahre mit weniger Beobachtungen als die Schwelle "
              "sind mit ⚠ markiert.", ""]  # fmt: skip
    years = sorted({y["year"] for y in result["yearly"]})
    for profile, label in result["profiles"].items():
        rows = []
        for asset_class in [*result["classes"], "all"]:
            cells = {
                y["year"]: y
                for y in result["yearly"]
                if y["profile"] == profile and y["asset_class"] == asset_class
            }
            if not cells:
                continue
            row = [CLASS_NAME[asset_class]]
            for year in years:
                y = cells.get(year)
                row.append(
                    "–"
                    if y is None or y["ic"] is None
                    else f"{de(y['ic'], '+.2f')} ({y['n']}){_flag(y['n'] >= result['min_signals'])}"
                )
            rows.append(row)
        lines += [f"### {label} (Horizont {primary[profile]} T)", ""]
        lines += _table(["Klasse", *years], rows)

    lines += ["## Abdeckung je Zeitraum", "",
              "Anteil der Scores (Profil Swing), in denen der Faktor einen Wert lieferte; Gewichte "
              "fehlender Faktoren werden renormiert. Retail-Sentiment, AAII und Short Interest "
              "haben keine bzw. kaum Historie vor 2024-11, COT reicht 15 Jahre zurück (ab 2013).", ""]  # fmt: skip
    for asset_class in result["classes"]:
        block = [c for c in result["coverage"] if c["asset_class"] == asset_class]
        if not block:
            continue
        factors = sorted({f for c in block for f in c["factors"]})
        rows = [
            [
                c["year"],
                f"{c['n']}",
                _pct(c["mean_coverage"], 0),
                *[_pct(c["factors"].get(f), 0) for f in factors],
            ]
            for c in block
        ]
        lines += [f"### {CLASS_NAME[asset_class]}", ""]
        lines += _table(
            ["Jahr", "Scores", "Ø Abdeckung", *[FACTOR_NAME.get(f, f) for f in factors]], rows
        )
    return "\n".join(lines).rstrip() + "\n\n" + TREND_APPENDIX.rstrip() + "\n\n" + LONGTERM_APPENDIX


def write_report(result: dict[str, Any], output_dir: Path, markdown: Path | None = None) -> dict:
    """Schreibt `backtest.json` und den Markdown-Report; gibt die Pfade zurück."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "backtest.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path = markdown or output_dir / "backtest-report.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
