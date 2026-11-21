"""Scorecard der Asset-Detailseite: Gruppen-Teilscores (−10…+10) und gruppierte Tabellenzeilen.

Alles stammt aus vorhandenen Daten: Teilscores und Eingangswerte aus `score_components`, aktuelle
Werte aus den Quelltabellen. Für Makrodaten gibt es keine kostenlosen Konsensprognosen, daher
Wert, Vorwert, Änderung und Datum statt Forecast/Surprise; echte Schätzung nur bei Earnings.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from edgefinder.api import schemas as s
from edgefinder.config import (
    Asset,
    AssetClass,
    Config,
    ForexAsset,
    IndexAsset,
    StockAsset,
)
from edgefinder.scoring.agreement import agreement as factor_agreement
from edgefinder.scoring.data import DataStore
from edgefinder.scoring.factors import macro as macro_factor

# Gruppe → Faktoren, die in den Teilscore eingehen
GROUPS: dict[str, tuple[str, ...]] = {
    "technical": ("trend", "seasonality"),
    "sentiment": ("retail_sentiment", "aaii", "short_interest"),
    "institutional": ("cot", "insider"),
    "macro": ("macro", "fundamentals", "earnings"),
}
SOON_DAYS = 2  # Stern, wenn der nächste Termin höchstens so viele Tage entfernt ist
EARNINGS_SOON_DAYS = 14
COT_RELEASE_LAG_DAYS = 10  # Stichtag (Dienstag) → Veröffentlichung am übernächsten Freitag
RETAIL_PREVIOUS_HOURS = 24
INDEX_SCORE_CATEGORIES = ("growth", "labor")  # nur diese gehen bei Indizes in den Score ein
CATEGORY_ORDER = ("growth", "inflation", "labor", "rates")
CATEGORY_LABEL = {
    "growth": "Wachstum",
    "inflation": "Inflation",
    "labor": "Arbeitsmarkt",
    "rates": "Zinsen und Dollar",
}
UNIT_BY_KEY = {  # sonst Prozent
    "payrolls": "k",
    "jolts": "k",
    "adp": "count",
    "jobless": "count",
    "dollar_index": "index",
    "consumer_confidence": "index",
    "philly_fed": "index",
    "empire_state": "index",
    "industry_confidence": "index",
}


@dataclass(frozen=True)
class Component:
    subscore: float | None
    effective_weight: float
    reason: str
    inputs: dict[str, Any]


def signal_of(score: float | None, threshold: float) -> s.Signal | None:
    if score is None:
        return None
    if score >= threshold:
        return "bullish"
    if score <= -threshold:
        return "bearish"
    return "neutral"


def tile_scores(
    components: dict[str, Component], threshold: float, is_stock: bool
) -> list[s.ScorecardTileOut]:
    labels = {
        "technical": "Technik",
        "sentiment": "Sentiment",
        "institutional": "Institutionell",
        "macro": "Fundamentals" if is_stock else "Makro",
    }
    tiles: list[s.ScorecardTileOut] = []
    for key, factors in GROUPS.items():
        used = [
            (f, components[f])
            for f in factors
            if f in components
            and components[f].subscore is not None
            and components[f].effective_weight > 0
        ]
        weight = sum(c.effective_weight for _, c in used)
        score = (
            round(sum(c.effective_weight * c.subscore for _, c in used) / weight * 10, 2)  # type: ignore[operator]
            if weight > 0
            else None
        )
        tiles.append(
            s.ScorecardTileOut(
                key=key,  # type: ignore[arg-type]
                label=labels[key],
                score=score,
                weight=round(weight, 4),
                signal=signal_of(None if score is None else score / 10, threshold),
                factors=[f for f, _ in used],
            )
        )
    return tiles


def _section(
    key: str,
    group: str,
    label: str,
    kind: str,
    rows: list[s.ScorecardRowOut],
    threshold: float,
    score: float | None = None,
    empty_reason: str | None = None,
    in_score: bool = True,
) -> s.ScorecardSectionOut:
    if score is None:
        scores = [r.score for r in rows if r.score is not None]
        score = sum(scores) / len(scores) if scores else None
    return s.ScorecardSectionOut(
        key=key,
        group=group,  # type: ignore[arg-type]
        label=label,
        kind=kind,  # type: ignore[arg-type]
        signal=signal_of(score, threshold),
        score=None if score is None else round(score, 3),
        rows=rows,
        empty_reason=None if rows else empty_reason,
        in_score=in_score,
    )


def _reason(components: dict[str, Component], *factors: str) -> str | None:
    for f in factors:
        if f in components:
            return components[f].reason
    return None


class Builder:
    def __init__(
        self,
        config: Config,
        conn: sqlite3.Connection,
        asset: Asset,
        profile: str,
        components: dict[str, Component],
        as_of: date,
    ) -> None:
        self.config = config
        self.conn = conn
        self.asset = asset
        self.profile = profile
        self.c = components
        self.as_of = as_of
        self.threshold = config.scoring.signal_threshold
        self.store = DataStore(conn, config)
        self.params = config.profiles[profile].params

    def sig(self, score: float | None) -> s.Signal | None:
        return signal_of(score, self.threshold)

    def sub(self, factor: str) -> float | None:
        return self.c[factor].subscore if factor in self.c else None

    # --- Technik ---------------------------------------------------------------------------
    def technical(self) -> list[s.ScorecardSectionOut]:
        rows: list[s.ScorecardRowOut] = []
        trend = self.c.get("trend")
        if trend and trend.subscore is not None:
            rows.append(
                s.ScorecardRowOut(
                    key="trend",
                    label="Chart-Trend",
                    unit="%",
                    value=trend.inputs.get("dist_to_slow_pct"),
                    signal=self.sig(trend.subscore),
                    score=round(trend.subscore, 3),
                    note=trend.reason,
                    text="Abstand zum langsamen Schnitt",
                    # Umkehr-Modus mit klarem Signal: Score erwartet Bewegung gegen den Kurstrend
                    counter_trend=trend.inputs.get("mode") == "reversal"
                    and abs(trend.subscore) >= self.threshold,
                )
            )
        season = self.c.get("seasonality")
        if season and season.subscore is not None:
            rows.append(
                s.ScorecardRowOut(
                    key="seasonality",
                    label="Saisonalität",
                    unit="%",
                    value=season.inputs.get("mean_return_pct"),
                    signal=self.sig(season.subscore),
                    score=round(season.subscore, 3),
                    note=season.reason,
                    text=f"Ø Rendite in {season.inputs.get('forward_days', '?')} Handelstagen",
                )
            )
        return [
            _section(
                "technical",
                "technical",
                "Technik",
                "indicator",
                rows,
                self.threshold,
                empty_reason=_reason(self.c, "trend", "seasonality") or "Keine Kursdaten.",
            )
        ]

    # --- Sentiment ---------------------------------------------------------------------------
    def _retail_row(self) -> s.ScorecardRowOut | None:
        symbol = getattr(self.asset, "myfxbook", None)
        if not symbol:
            return None
        rows = self.conn.execute(
            "SELECT observed_at, long_pct, short_pct FROM retail_sentiment WHERE source ="
            " 'myfxbook' AND symbol = ? ORDER BY observed_at DESC LIMIT 400",
            (symbol,),
        ).fetchall()
        if not rows:
            return None
        last = rows[0]
        change = None
        try:
            cutoff = (
                datetime.fromisoformat(last["observed_at"]) - timedelta(hours=RETAIL_PREVIOUS_HOURS)
            ).isoformat(timespec="seconds")
            older = next((r for r in rows if r["observed_at"] <= cutoff), None)
            change = round(last["long_pct"] - older["long_pct"], 2) if older else None
        except ValueError:
            pass
        score = self.sub("retail_sentiment")
        return s.ScorecardRowOut(
            key="retail",
            label="Privatanleger (Myfxbook)",
            unit="%",
            change_unit="pp",
            long_pct=round(last["long_pct"], 2),
            short_pct=round(last["short_pct"], 2),
            change=change,
            date=last["observed_at"][:10],
            signal=self.sig(score),
            score=None if score is None else round(score, 3),
            note=_reason(self.c, "retail_sentiment"),
        )

    def _aaii_row(self) -> s.ScorecardRowOut | None:
        if self.asset.asset_class not in (AssetClass.INDEX, AssetClass.STOCK):
            return None
        rows = self.conn.execute(
            "SELECT week_date, bullish, bearish FROM aaii_sentiment ORDER BY week_date DESC LIMIT 2"
        ).fetchall()
        if not rows:
            return None
        score = self.sub("aaii")
        change = round(rows[0]["bullish"] - rows[1]["bullish"], 2) if len(rows) > 1 else None
        return s.ScorecardRowOut(
            key="aaii",
            label="AAII-Umfrage (Privatanleger USA)",
            unit="%",
            change_unit="pp",
            long_pct=rows[0]["bullish"],
            short_pct=rows[0]["bearish"],
            change=change,
            date=rows[0]["week_date"],
            signal=self.sig(score),
            score=None if score is None else round(score, 3),
            note=_reason(self.c, "aaii"),
            next_date=(date.fromisoformat(rows[0]["week_date"]) + timedelta(days=7)).isoformat(),
        )

    def sentiment(self) -> list[s.ScorecardSectionOut]:
        crowd = [r for r in (self._retail_row(), self._aaii_row()) if r is not None]
        out = [
            _section(
                "crowd",
                "sentiment",
                "Crowd Sentiment",
                "crowd",
                crowd,
                self.threshold,
                empty_reason=_reason(self.c, "retail_sentiment", "aaii")
                or "Keine Sentiment-Daten.",
            )
        ]
        if isinstance(self.asset, StockAsset):
            si = self.c.get("short_interest")
            rows: list[s.ScorecardRowOut] = []
            if si and si.subscore is not None:
                rows.append(
                    s.ScorecardRowOut(
                        key="short_interest",
                        label="Short Interest",
                        unit="shares",
                        change_unit="%",
                        value=si.inputs.get("short_interest"),
                        change=si.inputs.get("change_pct"),
                        date=si.inputs.get("settlement_date"),
                        signal=self.sig(si.subscore),
                        score=round(si.subscore, 3),
                        note=si.reason,
                        text=(
                            f"{si.inputs['days_to_cover']:.1f} Tage bis zur Deckung"
                            if si.inputs.get("days_to_cover")
                            else None
                        ),
                    )
                )
            out.append(
                _section(
                    "short_interest",
                    "sentiment",
                    "Leerverkäufe",
                    "indicator",
                    rows,
                    self.threshold,
                    empty_reason=_reason(self.c, "short_interest") or "Keine Daten.",
                )
            )
        return out

    # --- Institutionell ----------------------------------------------------------------------
    def _cot_row(
        self,
        code: str,
        name: str,
        side: str | None,
        score: float | None,
        inputs: dict[str, Any] | None = None,
    ) -> s.ScorecardRowOut | None:
        reports = self.conn.execute(
            "SELECT report_date, noncomm_long, noncomm_short FROM cot_reports WHERE contract_code ="
            " ? AND report_date <= ? ORDER BY report_date DESC LIMIT 2",
            (code, self.as_of.isoformat()),
        ).fetchall()
        if not reports:
            return None

        def long_share(r: sqlite3.Row) -> float | None:
            total = r["noncomm_long"] + r["noncomm_short"]
            return r["noncomm_long"] / total * 100 if total else None

        now = long_share(reports[0])
        before = long_share(reports[1]) if len(reports) > 1 else None
        release = date.fromisoformat(reports[0]["report_date"]) + timedelta(
            days=COT_RELEASE_LAG_DAYS
        )
        net = reports[0]["noncomm_long"] - reports[0]["noncomm_short"]
        inputs = inputs or {}
        percentile = inputs.get("level_percentile")
        years = round(inputs["weeks"] / 52) if inputs.get("weeks") else None
        # Neutrale Kurzlesart (unabhängig von der Pille): Richtung, Netto und Perzentil der Historie
        net_text = f"{net:+,}".replace(",", ".")
        reading = f"Non-Commercials Netto-{'Long' if net >= 0 else 'Short'} ({net_text} Kontrakte)"
        if percentile is not None:
            window = f"{years}-Jahres-" if years else ""
            reading += f", {percentile:.0f} % im {window}Perzentil der eigenen Historie"
        return s.ScorecardRowOut(
            key=f"cot-{code}",
            label=name,
            side=side,
            unit="%",
            change_unit="pp",
            long_pct=None if now is None else round(now, 1),
            short_pct=None if now is None else round(100 - now, 1),
            change=None if now is None or before is None else round(now - before, 1),
            date=reports[0]["report_date"],
            signal=self.sig(score),
            score=None if score is None else round(score, 3),
            next_date=release.isoformat(),
            soon=0 <= (release - self.as_of).days <= SOON_DAYS,
            percentile=None if percentile is None else round(percentile, 1),
            text=reading,
            note=_reason(self.c, "cot") if side is None else None,
        )

    def institutional(self) -> list[s.ScorecardSectionOut]:
        asset = self.asset
        rows: list[s.ScorecardRowOut] = []
        cot = self.c.get("cot")
        if isinstance(asset, ForexAsset):
            for ccy in (asset.base, asset.quote):
                code = self.config.currencies[ccy].cftc_code
                sub = cot.inputs.get(ccy, {}).get("subscore") if cot else None
                row = (
                    self._cot_row(
                        code,
                        f"COT Positionierung {ccy}",
                        ccy,
                        sub,
                        cot.inputs.get(ccy) if cot else None,
                    )
                    if code
                    else None
                )
                if row:
                    rows.append(row)
            score = cot.subscore if cot else None
        elif isinstance(asset, StockAsset):
            score = None
        else:
            code = asset.cftc_code
            inputs = self.c["cot"].inputs if "cot" in self.c else None
            row = (
                self._cot_row(code, "COT Positionierung", None, self.sub("cot"), inputs)
                if code
                else None
            )
            if row:
                rows.append(row)
            score = self.sub("cot")
        if isinstance(asset, StockAsset):
            ins = self.c.get("insider")
            if ins and ins.subscore is not None:
                buys, sells = ins.inputs.get("buys", 0), ins.inputs.get("sells", 0)
                rows.append(
                    s.ScorecardRowOut(
                        key="insider",
                        label=f"Insider-Handel ({ins.inputs.get('lookback_days', '?')} Tage)",
                        unit="usd",
                        value=(ins.inputs.get("buy_value") or 0)
                        - (ins.inputs.get("sell_value") or 0),
                        signal=self.sig(ins.subscore),
                        score=round(ins.subscore, 3),
                        text=f"{buys} Käufe, {sells} Verkäufe (Nettowert)",
                        note=ins.reason,
                    )
                )
                score = ins.subscore
            return [
                _section(
                    "insider",
                    "institutional",
                    "Insider",
                    "indicator",
                    rows,
                    self.threshold,
                    score=score,
                    empty_reason=_reason(self.c, "insider") or "Keine Insider-Daten.",
                )
            ]
        reason = "Für dieses Asset gibt es keinen CFTC-Bericht."
        return [
            _section(
                "cot",
                "institutional",
                "Institutionelle Aktivität (COT)",
                "positioning",
                rows,
                self.threshold,
                score=score,
                empty_reason=_reason(self.c, "cot") or reason,
            )
        ]

    # --- Makro -------------------------------------------------------------------------------
    def _economy_rows(self, code: str, side: str | None, categories: tuple[str, ...]):
        params = self.params.get("macro", {})
        data = self.store.economy(code, self.as_of)
        out: dict[str, list[s.ScorecardRowOut]] = {}
        for key, ind in self.config.economies[code].indicators.items():
            if ind.category not in categories:
                continue
            series = data.indicators.get(key)
            values = macro_factor.transformed(series) if series else []
            if not values:
                continue
            scored = (
                macro_factor.indicator_score(series, self.as_of, params)
                if series and not ind.info_only
                else None
            )
            unit = UNIT_BY_KEY.get(key, "%")
            previous = values[-2][1] if len(values) > 1 else None
            out.setdefault(ind.category, []).append(
                s.ScorecardRowOut(
                    key=f"{code}-{key}",
                    label=ind.label,
                    side=side,
                    unit=unit,
                    change_unit="pp" if unit == "%" else None,
                    value=round(values[-1][1], 4),
                    previous=None if previous is None else round(previous, 4),
                    change=None if previous is None else round(values[-1][1] - previous, 4),
                    date=values[-1][0],
                    signal=self.sig(scored[0]) if scored else None,
                    score=round(scored[0], 3) if scored else None,
                    info_only=ind.info_only,
                )
            )
        return out

    def macro(self) -> list[s.ScorecardSectionOut]:
        asset = self.asset
        sections: list[s.ScorecardSectionOut] = []
        if isinstance(asset, StockAsset):
            return self.fundamentals() + self.earnings()
        if isinstance(asset, ForexAsset):
            sides = [
                (self.config.currencies[asset.base].economy, asset.base),
                (self.config.currencies[asset.quote].economy, asset.quote),
            ]
            categories = CATEGORY_ORDER
        elif isinstance(asset, IndexAsset):
            sides, categories = [(asset.economy, None)], CATEGORY_ORDER
        else:
            sides, categories = [("US", None)], CATEGORY_ORDER
        per_side = [(side, self._economy_rows(code, side, categories)) for code, side in sides]
        macro_inputs = self.c["macro"].inputs if "macro" in self.c else {}
        for category in categories:
            rows = [r for _, by_cat in per_side for r in by_cat.get(category, [])]
            info_only_index = (
                isinstance(asset, IndexAsset) and category not in INDEX_SCORE_CATEGORIES
            )
            if info_only_index:
                # Die Richtung (`higher_is`) gilt für Währungen; für Aktienindizes wäre eine Pille
                # irreführend. Nur Wert, Vorwert und Änderung zeigen.
                rows = [r.model_copy(update={"signal": None, "score": None}) for r in rows]
            score = None
            if isinstance(asset, ForexAsset):  # Basis − Quote, wie in der Engine
                mean = [
                    (sum(r.score for r in by.get(category, []) if r.score is not None) / n)
                    if (n := len([r for r in by.get(category, []) if r.score is not None]))
                    else None
                    for _, by in per_side
                ]
                if None not in mean:
                    score = max(-1.0, min(1.0, mean[0] - mean[1]))  # type: ignore[operator]
            elif isinstance(macro_inputs.get(category), dict):
                score = macro_inputs[category].get("score")
            sections.append(
                _section(
                    f"macro-{category}",
                    "macro",
                    CATEGORY_LABEL[category],
                    "indicator",
                    rows,
                    self.threshold,
                    score=score,
                    empty_reason="Keine aktuellen Daten für diese Kategorie.",
                    in_score=not info_only_index
                    and (
                        isinstance(asset, ForexAsset)
                        or category in macro_inputs
                        or (category == "rates" and "dollar" in macro_inputs)
                    ),
                )
            )
        return sections

    def fundamentals(self) -> list[s.ScorecardSectionOut]:
        comp = self.c.get("fundamentals")
        rows: list[s.ScorecardRowOut] = []
        if comp and comp.subscore is not None:
            i = comp.inputs
            if "growth" in i:
                g = i["growth"]
                rows.append(
                    s.ScorecardRowOut(
                        key="growth",
                        label="Umsatzwachstum (p. a.)",
                        unit="%",
                        value=g.get("cagr_pct"),
                        date=g.get("period_end"),
                        score=g.get("score"),
                        signal=self.sig(g.get("score")),
                    )
                )
            if "margin" in i:
                m = i["margin"]
                rows.append(
                    s.ScorecardRowOut(
                        key="margin",
                        label="Nettomarge",
                        unit="%",
                        change_unit="pp",
                        value=m.get("margin_pct"),
                        change=m.get("change_pts"),
                        previous=(
                            round(m["margin_pct"] - m["change_pts"], 2)
                            if m.get("margin_pct") is not None and m.get("change_pts") is not None
                            else None
                        ),
                        date=m.get("period_end"),
                        score=m.get("score"),
                        signal=self.sig(m.get("score")),
                    )
                )
            if "valuation" in i:
                v = i["valuation"]
                rows.append(
                    s.ScorecardRowOut(
                        key="valuation",
                        label="Bewertung (KGV)",
                        unit="x",
                        value=v.get("pe"),
                        score=v.get("score"),
                        signal=self.sig(v.get("score")),
                        text=(
                            f"Perzentil {v['percentile']:.0f} der eigenen Historie"
                            if v.get("percentile") is not None
                            else None
                        ),
                    )
                )
        return [
            _section(
                "fundamentals",
                "macro",
                "Geschäftszahlen",
                "indicator",
                rows,
                self.threshold,
                score=comp.subscore if comp else None,
                empty_reason=_reason(self.c, "fundamentals") or "Keine SEC-Daten.",
            )
        ]

    def earnings(self) -> list[s.ScorecardSectionOut]:
        asset = self.asset
        if not isinstance(asset, StockAsset):
            return []
        data = self.conn.execute(
            "SELECT earnings_date, eps_estimate, eps_actual, surprise_pct FROM earnings WHERE"
            " ticker = ? ORDER BY earnings_date DESC LIMIT 12",
            (asset.ticker,),
        ).fetchall()
        neutral = self.config.scoring.earnings_neutral_pct
        rows: list[s.ScorecardRowOut] = []
        past = [r for r in data if r["eps_actual"] is not None]
        upcoming = [
            r
            for r in data
            if r["eps_actual"] is None and r["earnings_date"] >= self.as_of.isoformat()
        ]
        if upcoming:
            nxt = min(upcoming, key=lambda r: r["earnings_date"])
            days = (date.fromisoformat(nxt["earnings_date"]) - self.as_of).days
            rows.append(
                s.ScorecardRowOut(
                    key=f"earn-{nxt['earnings_date']}",
                    label="Nächste Zahlen",
                    unit="usd",
                    estimate=nxt["eps_estimate"],
                    date=nxt["earnings_date"],
                    next_date=nxt["earnings_date"],
                    soon=days <= EARNINGS_SOON_DAYS,
                )
            )
        quarters = int(self.params.get("earnings", {}).get("quarters", 4))
        for r in past[: max(quarters, 4)]:
            surprise = r["surprise_pct"]
            rows.append(
                s.ScorecardRowOut(
                    key=f"earn-{r['earnings_date']}",
                    label="Gewinn je Aktie (EPS)",
                    unit="usd",
                    value=r["eps_actual"],
                    estimate=r["eps_estimate"],
                    surprise_pct=surprise,
                    date=r["earnings_date"],
                    signal=None
                    if surprise is None
                    else (
                        "bullish"
                        if surprise > neutral
                        else "bearish"
                        if surprise < -neutral
                        else "neutral"
                    ),
                )
            )
        comp = self.c.get("earnings")
        return [
            _section(
                "earnings",
                "macro",
                "Earnings",
                "earnings",
                rows,
                self.threshold,
                score=comp.subscore if comp else None,
                empty_reason=_reason(self.c, "earnings") or "Keine Earnings-Daten.",
            )
        ]


def load_components(
    conn: sqlite3.Connection, asset_id: str, profile: str
) -> tuple[str | None, dict[str, Component]]:
    row = conn.execute(
        "SELECT id, date FROM scores WHERE asset_id = ? AND profile = ? ORDER BY date DESC LIMIT 1",
        (asset_id, profile),
    ).fetchone()
    if row is None:
        return None, {}
    comps = conn.execute(
        "SELECT factor, subscore, effective_weight, reason, inputs FROM score_components WHERE"
        " score_id = ?",
        (row["id"],),
    ).fetchall()
    return row["date"], {
        c["factor"]: Component(
            c["subscore"], c["effective_weight"], c["reason"], json.loads(c["inputs"])
        )
        for c in comps
    }


def build_scorecard(
    config: Config, conn: sqlite3.Connection, asset: Asset, profile: str, today: date
) -> s.ScorecardOut:
    score_date, components = load_components(conn, asset.id, profile)
    builder = Builder(config, conn, asset, profile, components, today)
    sections = builder.technical() + builder.sentiment() + builder.institutional() + builder.macro()
    tiles = (
        tile_scores(components, config.scoring.signal_threshold, isinstance(asset, StockAsset))
        if components
        else []
    )
    technical = next((t for t in tiles if t.key == "technical" and t.score is not None), None)
    for section in sections:  # Technik-Kopfzeile = gewichteter Teilscore wie die Kachel
        if technical and section.key == "technical":
            section.score = round(technical.score / 10, 3)  # type: ignore[operator]
            section.signal = technical.signal
    return s.ScorecardOut(
        asset_id=asset.id,
        profile=profile,
        as_of=score_date,
        signal_threshold=config.scoring.signal_threshold,
        agreement=_agreement(config, conn, asset.id, profile, components),
        tiles=tiles,
        sections=sections,
    )


def _agreement(
    config: Config,
    conn: sqlite3.Connection,
    asset_id: str,
    profile: str,
    components: dict[str, Component],
) -> s.AgreementOut | None:
    """Faktor-Übereinstimmung aus den Teilscores des aktuellen Scores (Richtung = Gesamtscore)."""
    if not components:
        return None
    row = conn.execute(
        "SELECT score FROM scores WHERE asset_id = ? AND profile = ? ORDER BY date DESC LIMIT 1",
        (asset_id, profile),
    ).fetchone()
    if row is None:
        return None
    info = factor_agreement(
        [(c.subscore, c.effective_weight) for c in components.values()],
        row["score"],
        config.scoring.signal_threshold,
    )
    if info is None:
        return None
    return s.AgreementOut(
        **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in info.items()},
        threshold=config.backtest.calibration.agreement_threshold,
        high=info["weight_share"] is not None
        and info["weight_share"] >= config.backtest.calibration.agreement_threshold,
    )
