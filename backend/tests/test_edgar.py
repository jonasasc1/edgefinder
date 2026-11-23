from __future__ import annotations

import gzip
import json
from datetime import timedelta

import httpx
import pytest
from support import fixture_bytes, fixture_json, mock_client

from edgefinder.config import Secrets
from edgefinder.fetchers.edgar import (
    EdgarFetcher,
    parse_company_tickers,
    parse_facts,
    parse_form4,
    recent_form4,
)

CONTACT = "kontakt@example.invalid"
AAPL_FORM4 = {  # Accession (ohne Striche) → Fixture
    "000114036126000003": "edgar_form4_sale.xml",
    "000114036126000002": "edgar_form4_buy.xml",
    "000114036126000001": "edgar_form4_noopen.xml",
}


@pytest.fixture
def edgar_secrets() -> Secrets:
    return Secrets(_env_file=None, contact_email=CONTACT)  # type: ignore[call-arg]


class FakeSec:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.failing: set[str] = set()  # Pfadteile, die mit 500 antworten

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if any(part in path for part in self.failing):
            return httpx.Response(500)
        if path.endswith("company_tickers.json"):
            return httpx.Response(200, content=fixture_bytes("edgar_company_tickers.json"))
        if "/companyfacts/CIK0000320193" in path:
            return httpx.Response(200, content=fixture_bytes("edgar_companyfacts_aapl.json"))
        if "/submissions/CIK0000320193" in path:
            return httpx.Response(200, content=fixture_bytes("edgar_submissions_aapl.json"))
        if "/Archives/edgar/data/320193/" in path:
            accession = path.split("/")[-2]
            if path.rsplit("/", 1)[-1] in {"form4_a.xml", "form4_b.xml", "form4_c.xml"}:
                name = AAPL_FORM4[accession]
                return httpx.Response(200, content=fixture_bytes(name))
        return httpx.Response(404)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


def _fetcher(make_config, config_data, secrets, db, clock, fake, tickers=("AAPL",)):
    config_data["assets"]["stocks"] = [
        s for s in config_data["assets"]["stocks"] if s["ticker"] in tickers
    ]
    config = make_config(assets=config_data["assets"])
    return EdgarFetcher(
        config, secrets, db, client=mock_client(fake), sleep=clock.sleep, clock=clock
    )


# ---------------------------------------------------------------- Parser
def test_parse_company_tickers_keeps_first_entry_per_ticker() -> None:
    mapping = parse_company_tickers(fixture_json("edgar_company_tickers.json"))
    assert mapping["AAPL"] == (320193, "Apple Inc.")
    assert mapping["BRK-B"][0] == 1067983


def test_parse_facts_filters_forms_nulls_and_age() -> None:
    data = fixture_json("edgar_companyfacts_aapl.json")
    concepts = [
        "us-gaap:Revenues",
        "us-gaap:NetIncomeLoss",
        "us-gaap:Assets",
        "dei:EntityCommonStockSharesOutstanding",
        "us-gaap:DoesNotExist",
    ]
    rows = parse_facts(data, "AAPL", concepts, {"10-K", "10-Q"}, "2016-01-01")
    by_key = {(row[1], row[7], row[8]): row for row in rows}
    assert ("us-gaap:Revenues", "10-K", "2025-10-31") in by_key
    assert not any(row[7] in ("8-K", "10-Q/A") for row in rows)  # Formular nicht gewünscht
    assert not any(row[8] == "2010-10-27" for row in rows)  # zu alt
    assert not any(row[8] == "2026-01-30" for row in rows)  # ohne Wert
    assets = by_key["us-gaap:Assets", "10-K", "2025-10-31"]
    assert assets[3] == "" and assets[9] == 359241000000  # Bilanzwert ohne Periodenbeginn
    assert any(row[1] == "dei:EntityCommonStockSharesOutstanding" for row in rows)


def test_recent_form4_only_form4_in_window_with_raw_xml_name() -> None:
    found = recent_form4(fixture_json("edgar_submissions_aapl.json"), "2025-11-17")
    assert [item[0] for item in found] == [
        "0001140361-26-000003",
        "0001140361-26-000002",
        "0001140361-26-000001",
    ]
    assert found[0][2] == "form4_a.xml"  # XSL-Präfix entfernt


def test_parse_form4_keeps_only_open_market_trades() -> None:
    sale = parse_form4(fixture_bytes("edgar_form4_sale.xml"), "0001-26-1", "AAPL", "2026-11-10")
    assert sale == [
        (
            "0001-26-1",
            1,
            "AAPL",
            "Example Officer One",
            "Chief Example Officer",
            "2026-11-06",
            "S",
            0,
            1000.0,
            210.5,
            "2026-11-10",
        )
    ]  # M/F-Zeilen und die abgeleitete Tabelle (S, 999) fehlen
    buy = parse_form4(fixture_bytes("edgar_form4_buy.xml"), "0001-26-2", "AAPL", "2026-11-03")
    assert len(buy) == 1 and buy[0][6] == "P" and buy[0][7] == 1
    assert buy[0][4] == "Director"
    assert parse_form4(fixture_bytes("edgar_form4_noopen.xml"), "x", "AAPL", "d") == []


# ---------------------------------------------------------------- Fetcher
def test_full_run_stores_cik_fundamentals_and_insider_trades(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeSec()
    result = _fetcher(make_config, config_data, edgar_secrets, db, clock, fake).run()

    assert result.status == "success", result.errors
    assert db.execute("SELECT cik FROM sec_companies WHERE ticker='AAPL'").fetchone()[0] == 320193
    concepts = {r[0] for r in db.execute("SELECT concept FROM fundamentals")}
    assert {
        "us-gaap:Revenues",
        "us-gaap:NetIncomeLoss",
        "dei:EntityCommonStockSharesOutstanding",
    } <= concepts
    trades = db.execute(
        "SELECT transaction_code, acquired FROM insider_trades ORDER BY 1"
    ).fetchall()
    assert [tuple(t) for t in trades] == [("P", 1), ("S", 0)]
    seen = db.execute("SELECT COUNT(*), SUM(trades) FROM sec_filings_seen").fetchone()
    assert tuple(seen) == (3, 2)  # die Einreichung ohne P/S ist trotzdem als gesehen vermerkt
    # 1 Tickers + 1 Facts + 1 Submissions + 3 Form 4
    assert result.requests == 6
    # Rohdaten: Facts gzip-komprimiert, Form-4-XML unverändert
    keys = {r[0] for r in db.execute("SELECT key FROM raw_files WHERE source='edgar'")}
    assert {"company_tickers", "companyfacts_AAPL", "submissions_AAPL"} <= keys
    facts_path = db.execute("SELECT path FROM raw_files WHERE key='companyfacts_AAPL'").fetchone()[
        0
    ]
    assert facts_path.endswith(".json.gz")
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE path LIKE '%.xml'").fetchone()[0] == 3


def test_requests_carry_contact_user_agent_and_respect_pace(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeSec()
    _fetcher(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert all(CONTACT in r.headers["user-agent"] for r in fake.requests)
    assert all(r.headers["user-agent"].startswith("edgefinder/") for r in fake.requests)
    # 0,2 s Mindestabstand (= 5 Requests/s, halbes SEC-Limit)
    assert len([s for s in clock.sleeps if s >= 0.19]) >= len(fake.requests) - 1


def test_form4_url_points_to_raw_xml_in_archives(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeSec()
    _fetcher(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert "/Archives/edgar/data/320193/000114036126000003/form4_a.xml" in fake.paths()
    assert "/submissions/CIK0000320193.json" in fake.paths()
    assert "/api/xbrl/companyfacts/CIK0000320193.json" in fake.paths()


def test_second_run_is_incremental(make_config, config_data, edgar_secrets, db, clock) -> None:
    _fetcher(make_config, config_data, edgar_secrets, db, clock, FakeSec()).run()
    fake = FakeSec()
    clock.now += timedelta(days=1)
    result = _fetcher(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert result.status == "success"
    assert fake.paths() == ["/submissions/CIK0000320193.json"]  # nur der Einreichungsindex
    assert db.execute("SELECT COUNT(*) FROM insider_trades").fetchone()[0] == 2
    # nach Ablauf der Fristen werden CIK-Liste und Fundamentaldaten neu geladen
    fake = FakeSec()
    clock.now += timedelta(days=8)
    _fetcher(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert any(p.endswith("company_tickers.json") for p in fake.paths())
    assert any("companyfacts" in p for p in fake.paths())


def test_missing_contact_email_makes_no_request(make_config, config_data, db, clock) -> None:
    fake = FakeSec()
    empty = Secrets(_env_file=None)  # type: ignore[call-arg]
    result = _fetcher(make_config, config_data, empty, db, clock, fake).run()
    assert result.status == "error" and fake.requests == []
    assert "CONTACT_EMAIL" in result.errors[0]


def test_failing_form4_gives_partial_and_is_retried_next_run(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeSec()
    fake.failing = {"000114036126000002"}  # Kauf-Einreichung fällt aus
    result = _fetcher(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert result.status == "partial" and result.items > 0
    assert "0001140361-26-000002" in result.errors[0]
    assert [r[0] for r in db.execute("SELECT transaction_code FROM insider_trades")] == ["S"]
    assert db.execute("SELECT COUNT(*) FROM sec_filings_seen").fetchone()[0] == 2
    assert result.requests == 9  # Tickers, Facts, Submissions, 2 × XML ok, 4 Versuche für das 3.

    clock.now += timedelta(hours=6)
    again = _fetcher(make_config, config_data, edgar_secrets, db, clock, FakeSec()).run()
    assert again.status == "success"
    assert sorted(r[0] for r in db.execute("SELECT transaction_code FROM insider_trades")) == [
        "P",
        "S",
    ]


def test_sources_are_independent_per_ticker(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    """BRK-B liefert 404 (kein Fixture): AAPL wird trotzdem vollständig geholt."""
    fake = FakeSec()
    result = _fetcher(
        make_config, config_data, edgar_secrets, db, clock, fake, tickers=("AAPL", "BRK-B")
    ).run()
    assert result.status == "partial"
    assert any("BRK-B" in e for e in result.errors)
    assert db.execute("SELECT COUNT(*) FROM insider_trades WHERE ticker='AAPL'").fetchone()[0] == 2


def test_ticker_unknown_to_sec_is_reported(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeSec()
    result = _fetcher(
        make_config, config_data, edgar_secrets, db, clock, fake, tickers=("AAPL", "NVDA")
    ).run()
    assert result.status == "partial"
    assert any("NVDA" in e and "CIK" in e for e in result.errors)


def test_contact_email_is_scrubbed_from_errors(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fetcher = _fetcher(make_config, config_data, edgar_secrets, db, clock, FakeSec())
    assert CONTACT not in fetcher.scrub(f"Fehler bei {CONTACT}")


def test_raw_companyfacts_roundtrip(
    make_config, config_data, edgar_secrets, db, clock, tmp_path
) -> None:
    _fetcher(make_config, config_data, edgar_secrets, db, clock, FakeSec()).run()
    relative = db.execute("SELECT path FROM raw_files WHERE key='companyfacts_AAPL'").fetchone()[0]
    raw = (tmp_path / "raw" / relative).read_bytes()
    assert json.loads(gzip.decompress(raw))["entityName"] == "Apple Inc."


# ---------------------------------------------------------------- Vorgänger-CIKs (XOM-Fall)
XOM_OLD, XOM_NEW = 34088, 2115436
XOM_FORM4 = {  # Accession (ohne Striche) → Fixture, Pfad enthält die CIK des Einreichers
    (XOM_OLD, "000003408826000007"): "edgar_form4_sale.xml",
    (XOM_OLD, "000003408826000008"): "edgar_form4_buy.xml",
    (XOM_NEW, "000211543626000001"): "edgar_form4_noopen.xml",
    (XOM_OLD, "000211543626000001"): "edgar_form4_noopen.xml",
}


class FakeXom(FakeSec):
    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append(request)
        if any(part in path for part in self.failing):
            return httpx.Response(500)
        files = {
            f"/companyfacts/CIK{XOM_OLD:010d}": "edgar_companyfacts_xom_old.json",
            f"/companyfacts/CIK{XOM_NEW:010d}": "edgar_companyfacts_xom_new.json",
            f"/submissions/CIK{XOM_OLD:010d}": "edgar_submissions_xom_old.json",
            f"/submissions/CIK{XOM_NEW:010d}": "edgar_submissions_xom_new.json",
        }
        for part, name in files.items():
            if part in path:
                return httpx.Response(200, content=fixture_bytes(name))
        if path.endswith("company_tickers.json"):
            return httpx.Response(200, content=fixture_bytes("edgar_company_tickers.json"))
        if path.startswith("/Archives/edgar/data/"):
            _, _, _, _, cik, accession, _ = path.split("/")
            name = XOM_FORM4.get((int(cik), accession))
            if name:
                return httpx.Response(200, content=fixture_bytes(name))
        return httpx.Response(404)


def _xom_with(make_config, config_data, secrets, db, clock, fake, **kwargs):
    # make_config bekommt die geänderten Quellen über config_data["sources"]
    config_data["assets"]["stocks"] = [
        s for s in config_data["assets"]["stocks"] if s["ticker"] == "XOM"
    ]
    config_data["sources"]["edgar"]["options"]["predecessor_ciks"] = kwargs.get(
        "predecessors", {"XOM": [XOM_OLD]}
    )
    config = make_config(assets=config_data["assets"], sources=config_data["sources"])
    return EdgarFetcher(
        config, secrets, db, client=mock_client(fake), sleep=clock.sleep, clock=clock
    )


def _rows(db):
    return [
        tuple(r)
        for r in db.execute(
            "SELECT period_end, filed, value FROM fundamentals WHERE concept='us-gaap:Revenues'"
            " ORDER BY period_end, filed"
        )
    ]


def test_predecessor_cik_is_loaded_under_same_ticker(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeXom()
    result = _xom_with(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert result.status == "success", result.errors
    assert db.execute("SELECT cik FROM sec_companies WHERE ticker='XOM'").fetchone()[0] == XOM_NEW
    assert {r[0] for r in db.execute("SELECT DISTINCT ticker FROM fundamentals")} == {"XOM"}
    paths = fake.paths()
    assert f"/api/xbrl/companyfacts/CIK{XOM_OLD:010d}.json" in paths
    assert f"/submissions/CIK{XOM_OLD:010d}.json" in paths
    # Form 4 des Vorgängers wird unter dessen CIK abgerufen, gespeichert unter XOM
    assert "/Archives/edgar/data/34088/000003408826000007/form4_a.xml" in paths
    trades = db.execute("SELECT ticker, transaction_code FROM insider_trades ORDER BY 2").fetchall()
    assert [tuple(t) for t in trades] == [("XOM", "P"), ("XOM", "S")]
    keys = {r[0] for r in db.execute("SELECT key FROM raw_files WHERE source='edgar'")}
    assert {"companyfacts_XOM", f"companyfacts_XOM_{XOM_OLD}"} <= keys
    assert {"submissions_XOM", f"submissions_XOM_{XOM_OLD}"} <= keys


def test_predecessor_duplicates_do_not_count_twice(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    from edgefinder.scoring.factors.fundamentals import Fact, ttm_series

    _xom_with(make_config, config_data, edgar_secrets, db, clock, FakeXom()).run()
    rows = _rows(db)
    # FY2025: gleiche Einreichung bei alter und neuer CIK → eine Zeile (gleicher Schlüssel)
    assert [r for r in rows if r[0] == "2025-12-31"] == [("2025-12-31", "2026-02-20", 360000.0)]
    # FY2024: Neu-Einreichung der Holding mit anderem Datum bleibt als eigene Version erhalten
    assert [r for r in rows if r[0] == "2024-12-31"] == [
        ("2024-12-31", "2025-02-20", 350000.0),
        ("2024-12-31", "2026-02-20", 351000.0),
    ]
    assert {r[0] for r in rows} == {"2023-12-31", "2024-12-31", "2025-12-31", "2026-03-31"}
    # Faktor-Eingang: je Periode genau ein TTM-Wert, jüngste Einreichung gewinnt, aufsteigend
    facts = [
        Fact(start, end, value, filed)
        for start, end, value, filed in db.execute(
            "SELECT period_start, period_end, value, filed FROM fundamentals"
            " WHERE concept='us-gaap:Revenues'"
        )
    ]
    series = ttm_series(facts)
    assert [d for d, _ in series] == ["2023-12-31", "2024-12-31", "2025-12-31"]
    assert dict(series)["2024-12-31"] == 351000.0
    # Look-ahead: vor der Holding-Neueinreichung zählt der Wert der alten CIK
    early = ttm_series([f for f in facts if f.filed <= "2025-12-31"])
    assert dict(early)["2024-12-31"] == 350000.0


def test_predecessor_form4_accession_counted_once(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeXom()
    _xom_with(make_config, config_data, edgar_secrets, db, clock, fake).run()
    # dieselbe Accession steht in beiden submissions: nur einmal geladen
    xml = [p for p in fake.paths() if p.endswith("000211543626000001/form4_c.xml")]
    assert len(xml) == 1
    assert db.execute("SELECT COUNT(*) FROM sec_filings_seen").fetchone()[0] == 3


def test_failing_predecessor_gives_partial_and_keeps_others(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeXom()
    fake.failing = {f"CIK{XOM_OLD:010d}"}
    result = _xom_with(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert result.status == "partial"
    assert sum(f"Vorgänger-CIK {XOM_OLD}" in e for e in result.errors) == 2  # Facts + Form 4
    assert {r[0] for r in db.execute("SELECT period_end FROM fundamentals")} >= {"2026-03-31"}
    assert db.execute("SELECT COUNT(*) FROM sec_filings_seen").fetchone()[0] == 1  # aktuelle CIK
    # nächster Lauf (Vorgänger-Frist nie gesetzt) holt es nach
    clock.now += timedelta(hours=6)
    again = _xom_with(make_config, config_data, edgar_secrets, db, clock, FakeXom()).run()
    assert again.status == "success"
    assert db.execute("SELECT COUNT(*) FROM insider_trades").fetchone()[0] == 2


def test_predecessor_run_is_idempotent_and_respects_refresh(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    _xom_with(make_config, config_data, edgar_secrets, db, clock, FakeXom()).run()
    before = (_rows(db), db.execute("SELECT COUNT(*) FROM insider_trades").fetchone()[0])
    fake = FakeXom()
    clock.now += timedelta(days=1)
    result = _xom_with(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert result.status == "success"
    # keine großen companyfacts neu, nur die beiden Einreichungsindizes
    assert sorted(fake.paths()) == sorted(
        [f"/submissions/CIK{XOM_NEW:010d}.json", f"/submissions/CIK{XOM_OLD:010d}.json"]
    )
    assert (_rows(db), db.execute("SELECT COUNT(*) FROM insider_trades").fetchone()[0]) == before
    # nach Ablauf der Frist wieder beide companyfacts, Ergebnis unverändert
    fake = FakeXom()
    clock.now += timedelta(days=4)
    _xom_with(make_config, config_data, edgar_secrets, db, clock, fake).run()
    assert sum("companyfacts" in p for p in fake.paths()) == 2
    assert _rows(db) == before[0]


def test_predecessor_equal_to_current_cik_is_ignored(
    make_config, config_data, edgar_secrets, db, clock
) -> None:
    fake = FakeXom()
    fetcher = _xom_with(
        make_config, config_data, edgar_secrets, db, clock, fake, predecessors={"XOM": [XOM_NEW]}
    )
    assert fetcher.run().status == "success"
    assert sum("companyfacts" in p for p in fake.paths()) == 1
