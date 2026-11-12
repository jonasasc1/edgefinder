"""Notifier-Schnittstelle. Kanäle (z. B. Web-Push) implementieren `Notifier`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    asset_id: str | None = None
    url: str | None = None


class Notifier(Protocol):
    def send(self, notification: Notification) -> None:
        """Stellt eine Benachrichtigung zu. Fehler dürfen den Aufrufer nicht abbrechen."""
        ...


class NullNotifier:
    """Platzhalter, solange kein Kanal konfiguriert ist: verwirft alles."""

    def send(self, notification: Notification) -> None:
        return None
