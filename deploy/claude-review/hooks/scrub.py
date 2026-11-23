# ruff: noqa: E501  (lange Muster)
"""Schwärzt Secrets und maskiert E-Mail-Adressen (nur Standardbibliothek, ohne Abhängigkeiten).

Wird vom Paketbau des Prüfagenten (`claude_review.py`) benutzt. Eine **byte-gleiche Kopie** liegt in
`deploy/claude-review/hooks/scrub.py` (der Hook läuft ohne das edgefinder-Paket; ein Test stellt die
Gleichheit sicher). Nach Änderungen: `cp backend/edgefinder/claude_scrub.py deploy/claude-review/hooks/scrub.py`.
"""

from __future__ import annotations

import re

REDACTED = "[GESCHWAERZT]"

# Reihenfolge: spezifische Muster zuerst. Jedes Muster ersetzt nur den geheimen Teil.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}"), REDACTED),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), REDACTED),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"), REDACTED),
    (
        re.compile(r"(?i)\b(bearer|basic)(\s+)[A-Za-z0-9._~+/=\-]{8,}"),
        r"\1\2" + REDACTED,
    ),
    (
        re.compile(
            r"(?i)([?&;](?:api[_-]?key|apikey|key|token|access[_-]?token|secret|password|sig|signature|auth)=)[^&\s\"'<>]+"
        ),
        r"\1" + REDACTED,
    ),
    (re.compile(r"(?i)(://[^/\s:@]+:)[^@\s/]+(@)"), r"\1" + REDACTED + r"\2"),
    (
        re.compile(
            r"(?i)(\b[A-Za-z0-9_.\-]*(?:api[_-]?key|token|secret|passwd|password|authorization|credential)[A-Za-z0-9_.\-]*"
            r"[\"']?\s*[:=]\s*[\"']?)(?!\[GESCHWAERZT\])[^\s\"',;}]{4,}"
        ),
        r"\1" + REDACTED,
    ),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"
        ),
        REDACTED,
    ),
)
_EMAIL = re.compile(
    r"\b([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*@([A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+)\b"
)


def scrub_secrets(text: str) -> str:
    """Nur Secrets schwärzen (für Quelltext, wo E-Mail-Adressen Testdaten sind)."""
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def mask_emails(text: str) -> str:
    """`jonas@example.com` → `j***@example.com`."""
    return _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)


def scrub(text: str) -> str:
    """Secrets schwärzen und E-Mail-Adressen maskieren (Logs, Berichte, Protokolle)."""
    return mask_emails(scrub_secrets(text))
