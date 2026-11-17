"""Datenquellen-Fetcher. `FETCHERS` ordnet die CLI-Namen den Klassen zu."""

from edgefinder.fetchers.aaii import AaiiFetcher
from edgefinder.fetchers.base import Fetcher, FetchError, RunResult
from edgefinder.fetchers.cftc import CftcFetcher
from edgefinder.fetchers.edgar import EdgarFetcher
from edgefinder.fetchers.eurostat import EcbFetcher, EurostatFetcher
from edgefinder.fetchers.finra import FinraFetcher
from edgefinder.fetchers.fred import FredFetcher
from edgefinder.fetchers.myfxbook import MyfxbookFetcher
from edgefinder.fetchers.prices import PricesFetcher

FETCHERS: dict[str, type[Fetcher]] = {
    "cftc": CftcFetcher,
    "fred": FredFetcher,
    "eurostat": EurostatFetcher,
    "ecb": EcbFetcher,
    "prices": PricesFetcher,
    "myfxbook": MyfxbookFetcher,
    "aaii": AaiiFetcher,
    "edgar": EdgarFetcher,
    "finra": FinraFetcher,
}

__all__ = ["FETCHERS", "FetchError", "Fetcher", "RunResult"]
