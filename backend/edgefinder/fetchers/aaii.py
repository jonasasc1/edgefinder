"""AAII Sentiment Survey: Bullish/Neutral/Bearish je Woche, von der öffentlichen Ergebnisseite.

Die Seite zeigt die aktuelle Woche und die letzten Wochen; die Historie bauen wir selbst auf.
Ist der Abruf blockiert (HTTP 403/429, Bot-Schutz-Seite statt Ergebnissen), gibt es einen
Fehler – bewusst kein Umgehungsversuch und kein Ersatz.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher, iso

_DATE_DIV = re.compile(r'<div class="date">\s*([^<]*?)\s*</div>')
_WEEK_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_BAR = re.compile(r'<div class="bar (bullish|neutral|bearish)"[^>]*>\s*([\d.]+)%\s*</div>')
_CURRENT_WEEK = re.compile(r"Week ending ([A-Z][a-z]+ \d{1,2}, \d{4})")
_CURRENT_BAR = re.compile(
    r'<div class="ssv2-slabel (bull|neut|bear)">.*?<div class="ssv2-snum \1">\s*([\d.]+)%\s*</div>',
    re.S,
)
_CURRENT_KEY = {"bull": "bullish", "neut": "neutral", "bear": "bearish"}


def parse_survey(html: str) -> dict[str, tuple[float, float, float]]:
    """HTML → {Wochenende (ISO): (bullish, neutral, bearish)}; leer, wenn nichts erkannt wird."""
    weeks: dict[str, tuple[float, float, float]] = {}
    marks = list(_DATE_DIV.finditer(html))  # auch „Historical Averages“ u. Ä. als Abschnittsgrenze
    for mark, following in zip(marks, [*marks[1:], None], strict=False):
        raw_date = mark.group(1)
        if not _WEEK_DATE.match(raw_date):
            continue
        segment = html[mark.end() : following.start() if following else mark.end() + 700]
        values = {name: float(value) for name, value in _BAR.findall(segment)}
        if set(values) != {"bullish", "neutral", "bearish"}:
            continue
        month, day, year = (int(part) for part in raw_date.split("/"))
        weeks[date(year, month, day).isoformat()] = (
            values["bullish"],
            values["neutral"],
            values["bearish"],
        )
    current_week = _CURRENT_WEEK.search(html)
    current = {_CURRENT_KEY[key]: float(value) for key, value in _CURRENT_BAR.findall(html)}
    if current_week and set(current) == {"bullish", "neutral", "bearish"}:
        week = datetime.strptime(current_week.group(1), "%B %d, %Y").date().isoformat()
        weeks[week] = (current["bullish"], current["neutral"], current["bearish"])
    return weeks


class AaiiFetcher(Fetcher):
    source = "aaii"

    def fetch(self) -> int:
        # Ehrlicher, beschreibender User-Agent (kein Browser-Vortäuschen). Der nackte Standard-UA
        # „edgefinder/0.1“ wurde vom Bot-Schutz der Seite mit HTTP 403 abgewiesen.
        headers = {"User-Agent": self.options["user_agent"]}
        response = self.http.get(self.options["url"], headers=headers)
        self.save_raw("sentimentsurvey", response.content, ".html")
        weeks = parse_survey(response.text)
        if not weeks:
            raise ValueError(
                "keine Umfrageergebnisse auf der Seite erkannt (Bot-Schutz oder Layoutänderung)"
            )
        rows = []
        for week, (bullish, neutral, bearish) in sorted(weeks.items()):
            total = bullish + neutral + bearish
            if not 98.0 <= total <= 102.0:  # Rundung ±1; alles andere ist kein Ergebnis
                with self.unit(f"Woche {week}"):
                    raise ValueError(f"Summe {total:.1f} % statt ≈100 %")
                continue
            rows.append((week, bullish, neutral, bearish, iso(self.clock())))
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT INTO aaii_sentiment (week_date, bullish, neutral, bearish, fetched_at)"
                " VALUES (?,?,?,?,?) ON CONFLICT (week_date) DO UPDATE SET"
                " bullish = excluded.bullish, neutral = excluded.neutral,"
                " bearish = excluded.bearish, fetched_at = excluded.fetched_at",
                rows,
            )
        return len(rows)
