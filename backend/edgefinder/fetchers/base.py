"""Gemeinsame Grundlage aller Fetcher.

- `HttpClient`: httpx mit Retry/Backoff und Rate-Limit je Quelle (Tabelle `request_log`)
- `Fetcher`: Lauf-Protokoll (`fetch_runs`), Rohdaten-Ablage (`raw_files`), Fehlerisolation
  je Einheit (Serie, Symbol, …), sodass ein Ausfall nichts anderes blockiert.

Secrets (API-Keys) stehen teils in URLs. Deshalb enthalten Fehlermeldungen und Logs nie die
Query, nur Pfad und Statuscode, und `Fetcher.scrub` schwärzt bekannte Secret-Werte.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from edgefinder.config import Config, RetryConfig, Secrets, SourceConfig
from edgefinder.db import transaction

log = logging.getLogger(__name__)

# httpx protokolliert jeden Request mit vollständiger URL auf INFO – inklusive API-Key in der
# Query. Diese Logger bleiben deshalb immer auf WARNING oder höher.
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
MAX_ERROR_LENGTH = 2000
USER_AGENT = "edgefinder/0.1"


class FetchError(Exception):
    """Abruf fehlgeschlagen (Meldung enthält nie Secrets)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RateLimitExceeded(FetchError):
    """Tageslimit einer Quelle ausgeschöpft."""


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime, timespec: str = "seconds") -> str:
    return moment.astimezone(UTC).isoformat(timespec=timespec)


class RateLimiter:
    """Mindestabstand und optionales Tageslimit je Quelle, persistiert in `request_log`.

    Der Abstand gilt damit auch zwischen getrennten Prozessen (z. B. zwei Timer-Läufen).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        source: str,
        config: SourceConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._conn = conn
        self._source = source
        self._min_interval = config.min_interval_seconds
        self._daily_limit = config.daily_request_limit
        self._sleep = sleep
        self._clock = clock

    def wait(self) -> None:
        """Wartet bis zum nächsten erlaubten Request und protokolliert ihn."""
        now = self._clock()
        if self._daily_limit is not None:
            since = iso(now - timedelta(hours=24), "microseconds")
            used = self._conn.execute(
                "SELECT COUNT(*) FROM request_log WHERE source = ? AND requested_at > ?",
                (self._source, since),
            ).fetchone()[0]
            if used >= self._daily_limit:
                raise RateLimitExceeded(
                    f"{self._source}: Tageslimit von {self._daily_limit} Requests erreicht"
                )
        row = self._conn.execute(
            "SELECT MAX(requested_at) FROM request_log WHERE source = ?", (self._source,)
        ).fetchone()
        if row[0] is not None:
            elapsed = (now - datetime.fromisoformat(row[0])).total_seconds()
            if 0 <= elapsed < self._min_interval:
                self._sleep(self._min_interval - elapsed)
        self._conn.execute(
            "INSERT INTO request_log (source, requested_at) VALUES (?, ?)",
            (self._source, iso(self._clock(), "microseconds")),
        )


class HttpClient:
    """GET-Requests mit Rate-Limit, Retry und Exponential Backoff."""

    def __init__(
        self,
        source: str,
        limiter: RateLimiter,
        retry: RetryConfig,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.source = source
        self.requests = 0
        self._limiter = limiter
        self._retry = retry
        self._sleep = sleep
        self._client = client or httpx.Client(
            timeout=retry.timeout_seconds,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        delay = self._retry.backoff_seconds * 2 ** (attempt - 1)
        if response is not None:
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isdigit():
                delay = max(delay, float(retry_after))
        return min(delay, self._retry.max_backoff_seconds)

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        return self.request("GET", url, params=params, headers=headers)

    def post_json(
        self,
        url: str,
        payload: Any,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """POST mit JSON-Body (z. B. FINRA-Abfrage-API); gleiche Regeln wie `get`."""
        return self.request("POST", url, headers=headers, json=payload)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        path = httpx.URL(url).path  # ohne Query: dort kann ein API-Key stehen
        failure = "unbekannt"
        for attempt in range(1, self._retry.attempts + 1):
            self._limiter.wait()
            self.requests += 1
            response: httpx.Response | None = None
            try:
                response = self._client.request(
                    method, url, params=params, headers=headers, json=json
                )
            except httpx.TransportError as exc:
                failure = f"{type(exc).__name__} bei {path}"
            else:
                if response.status_code < 400:
                    return response
                failure = f"HTTP {response.status_code} bei {path}"
                if response.status_code not in RETRYABLE_STATUS:
                    raise FetchError(f"{self.source}: {failure}", response.status_code)
            if attempt == self._retry.attempts:
                break
            delay = self._delay(attempt, response)
            log.warning(
                "%s: %s (Versuch %d/%d), neuer Versuch in %.1f s",
                self.source,
                failure,
                attempt,
                self._retry.attempts,
                delay,
            )
            self._sleep(delay)
        raise FetchError(f"{self.source}: {failure} nach {self._retry.attempts} Versuchen")


def call_with_retry[T](
    source: str,
    func: Callable[[], T],
    limiter: RateLimiter,
    retry: RetryConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
    on_request: Callable[[], None] = lambda: None,
) -> T:
    """Wie `HttpClient.get`, für Bibliotheken mit eigenem HTTP (yfinance).

    Jede Ausnahme von `func` gilt als vorübergehend und wird mit Backoff wiederholt.
    """
    failure = "unbekannt"
    for attempt in range(1, retry.attempts + 1):
        limiter.wait()
        on_request()
        try:
            return func()
        except Exception as exc:  # Bibliotheksfehler sind nicht einheitlich typisiert
            failure = f"{type(exc).__name__}: {exc}"
        if attempt == retry.attempts:
            break
        delay = min(retry.backoff_seconds * 2 ** (attempt - 1), retry.max_backoff_seconds)
        log.warning("%s: %s (Versuch %d/%d)", source, failure, attempt, retry.attempts)
        sleep(delay)
    raise FetchError(f"{source}: {failure} nach {retry.attempts} Versuchen")


@dataclass
class RunResult:
    run_id: int
    source: str
    status: str  # success | partial | error
    items: int
    requests: int
    errors: list[str] = field(default_factory=list)


class Fetcher:
    """Basisklasse: ein Fetcher je Quelle. Unterklassen implementieren `fetch()`."""

    source: str  # Schlüssel in config.sources

    def __init__(
        self,
        config: Config,
        secrets: Secrets,
        conn: sqlite3.Connection,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.conn = conn
        self.source_config = config.sources[self.source]
        self.options = self.source_config.options
        self.retry = config.retry_for(self.source)
        self.clock = clock
        self.sleep = sleep
        self.limiter = RateLimiter(conn, self.source, self.source_config, sleep=sleep, clock=clock)
        self.http = HttpClient(self.source, self.limiter, self.retry, client=client, sleep=sleep)
        self.errors: list[str] = []
        self.run_id: int | None = None
        self.extra_requests = 0  # Requests außerhalb von `self.http` (z. B. yfinance)

    # ------------------------------------------------------------ Ablauf
    def fetch(self) -> int:
        """Holt und speichert die Daten; gibt die Anzahl gespeicherter Zeilen zurück."""
        raise NotImplementedError

    def run(self) -> RunResult:
        started = self.clock()
        cursor = self.conn.execute(
            "INSERT INTO fetch_runs (source, started_at, status) VALUES (?, ?, 'running')",
            (self.source, iso(started)),
        )
        self.run_id = cursor.lastrowid
        items = 0
        try:
            items = self.fetch()
        except Exception as exc:  # Quelle fällt aus, andere Quellen laufen weiter
            log.exception("%s: Lauf abgebrochen", self.source)
            self.errors.append(self.scrub(f"{type(exc).__name__}: {exc}"))
        finally:
            self.http.close()
        if not self.errors:
            status = "success"
        elif items > 0:
            status = "partial"
        else:
            status = "error"
        requests = self.http.requests + self.extra_requests
        error_text = "; ".join(self.errors)[:MAX_ERROR_LENGTH] or None
        self.conn.execute(
            "UPDATE fetch_runs SET finished_at = ?, status = ?, items = ?, requests = ?, error = ?"
            " WHERE id = ?",
            (iso(self.clock()), status, items, requests, error_text, self.run_id),
        )
        return RunResult(self.run_id, self.source, status, items, requests, list(self.errors))

    @contextmanager
    def unit(self, name: str) -> Iterator[None]:
        """Fehler einer Einheit (Serie, Symbol, …) sammeln statt den Lauf abzubrechen."""
        try:
            yield
        except Exception as exc:
            message = self.scrub(f"{name}: {type(exc).__name__}: {exc}")
            log.warning("%s: %s", self.source, message)
            self.errors.append(message)

    def scrub(self, text: str) -> str:
        """Schwärzt Secret-Werte in Texten für Logs und Fehlerfelder."""
        for value in (
            self.secrets.fred_api_key,
            self.secrets.cftc_app_token,
            self.secrets.myfxbook_email,
            self.secrets.myfxbook_password,
            self.secrets.contact_email,
        ):
            if value is not None and value.get_secret_value():
                text = text.replace(value.get_secret_value(), "***")
        return text

    # ------------------------------------------------------------ Rohdaten
    def save_raw(self, key: str, content: bytes, suffix: str = ".json") -> Path:
        """Legt die Rohantwort unter raw_dir/<quelle>/<datum>/ ab und trägt sie in raw_files ein."""
        now = self.clock()
        safe = re.sub(r"[^A-Za-z0-9._=-]+", "_", key).strip("_")[:80] or "data"
        digest = hashlib.sha256(content).hexdigest()
        name = f"{safe}_{hashlib.sha256(key.encode()).hexdigest()[:8]}_{now:%H%M%S}{suffix}"
        relative = Path(self.source) / f"{now:%Y-%m-%d}" / name
        target = self.config.storage.raw_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO raw_files (run_id, source, key, path, sha256, bytes, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    self.run_id,
                    self.source,
                    key,
                    str(relative),
                    digest,
                    len(content),
                    iso(now),
                ),
            )
        return target

    # ------------------------------------------------------------ Zustand
    def get_state(self, key: str) -> tuple[str, str] | None:
        """Wert und Zeitpunkt (`updated_at`) aus `source_state`, falls vorhanden."""
        row = self.conn.execute(
            "SELECT value, updated_at FROM source_state WHERE source = ? AND key = ?",
            (self.source, key),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def set_state(self, key: str, value: str) -> None:
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO source_state (source, key, value, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (source, key) DO UPDATE SET value = excluded.value,"
                " updated_at = excluded.updated_at",
                (self.source, key, value, iso(self.clock())),
            )

    def clear_state(self, key: str) -> None:
        with transaction(self.conn):
            self.conn.execute(
                "DELETE FROM source_state WHERE source = ? AND key = ?", (self.source, key)
            )

    # ------------------------------------------------------------ Hilfen
    def history_start(self, years: int | None = None) -> datetime:
        years = years if years is not None else int(self.options.get("history_years", 15))
        return self.clock() - timedelta(days=round(365.25 * years))
