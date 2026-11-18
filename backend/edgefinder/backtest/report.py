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
              "haben keine bzw. kaum Historie vor 2024-11, COT reicht 6 Jahre zurück.", ""]  # fmt: skip
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
    return "\n".join(lines).rstrip() + "\n"


def write_report(result: dict[str, Any], output_dir: Path, markdown: Path | None = None) -> dict:
    """Schreibt `backtest.json` und den Markdown-Report; gibt die Pfade zurück."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "backtest.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path = markdown or output_dir / "backtest-report.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
