"""Push: how the desk reaches Max when something needs him.

A push is the one outbound request the desk makes that is not a read, so it
gets the same treatment the Hyperliquid POST got: confined, pinned, and
asserted. `NOTIFY_HOSTS` is the whole set of places a push may go, and
`tests/test_boundary.py` checks that no other host appears in this module
and that no market host appears in `NOTIFY_HOSTS`. A push service cannot
place an order, which is the point of letting only push services through.

Dedup lives here too. A stuck condition — a dark source, a PENDING ticket
nobody has challenged — should tell Max once per cooldown, not every poll.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .adapters.base import FetchError, fetch_json

# The only hosts a push may target. Adding one is a visible diff.
NOTIFY_HOSTS = ("ntfy.sh", "api.pushover.net")

NTFY_URL = "https://ntfy.sh"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

DEFAULT_COOLDOWN = timedelta(hours=4)


class NotifyError(Exception):
    """A push could not be delivered. The daemon logs it and carries on."""


@dataclass(frozen=True)
class Push:
    key: str
    title: str
    message: str
    priority: str = "default"   # ntfy: min | low | default | high | urgent


def configured() -> str | None:
    """Which service the environment names, or None."""
    if os.environ.get("NTFY_TOPIC"):
        return "ntfy"
    if os.environ.get("PUSHOVER_TOKEN") and os.environ.get("PUSHOVER_USER"):
        return "pushover"
    return None


def send(push: Push, *, dry_run: bool = False) -> str:
    """Deliver one push. Returns the service used, or 'dry-run'."""
    service = configured()
    if dry_run or service is None:
        return "dry-run" if dry_run else "unconfigured"
    if service == "ntfy":
        base = os.environ.get("NTFY_URL", NTFY_URL).rstrip("/")
        _assert_allowed(base)
        body = {
            "topic": os.environ["NTFY_TOPIC"],
            "title": push.title,
            "message": push.message,
            "priority": _ntfy_priority(push.priority),
        }
        headers = {}
        token = os.environ.get("NTFY_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            fetch_json(base, body=body, headers=headers, timeout=10.0, retries=1)
        except FetchError as exc:
            raise NotifyError(_redact(str(exc), token)) from exc
        return "ntfy"
    _assert_allowed(PUSHOVER_URL)
    body = {
        "token": os.environ["PUSHOVER_TOKEN"],
        "user": os.environ["PUSHOVER_USER"],
        "title": push.title,
        "message": push.message,
        "priority": _pushover_priority(push.priority),
    }
    try:
        fetch_json(PUSHOVER_URL, body=body, timeout=10.0, retries=1)
    except FetchError as exc:
        raise NotifyError(
            _redact(_redact(str(exc), body["token"]), body["user"])
        ) from exc
    return "pushover"


class Dedup:
    """Once per cooldown per key. State is a small JSON file so it survives
    a daemon restart; losing it costs at most one repeat push."""

    def __init__(self, path: str | Path, cooldown: timedelta = DEFAULT_COOLDOWN):
        self.path = Path(path)
        self.cooldown = cooldown
        self._sent: dict[str, datetime] = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._sent = {k: datetime.fromisoformat(v) for k, v in raw.items()}
            except (ValueError, OSError):
                self._sent = {}

    def should_send(self, key: str, *, now: datetime) -> bool:
        last = self._sent.get(key)
        return last is None or now - last >= self.cooldown

    def mark(self, key: str, *, now: datetime) -> None:
        self._sent[key] = now
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({k: v.isoformat() for k, v in self._sent.items()}, indent=2),
            encoding="utf-8",
        )

    def clear(self, key: str) -> None:
        """A condition resolved; the next occurrence should push again."""
        if key in self._sent:
            del self._sent[key]
            self.path.write_text(
                json.dumps({k: v.isoformat() for k, v in self._sent.items()}, indent=2),
                encoding="utf-8",
            )


def deliver(
    pushes: list[Push], dedup: Dedup, *, now: datetime, dry_run: bool = False
) -> list[tuple[Push, str]]:
    """Send what the cooldown allows; return (push, outcome) for the log."""
    out: list[tuple[Push, str]] = []
    for push in pushes:
        if not dedup.should_send(push.key, now=now):
            out.append((push, "suppressed"))
            continue
        try:
            outcome = send(push, dry_run=dry_run)
        except NotifyError as exc:
            out.append((push, f"failed: {exc}"))
            continue
        if outcome not in ("unconfigured",):
            dedup.mark(push.key, now=now)
        out.append((push, outcome))
    return out


def _assert_allowed(url: str) -> None:
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":")[0].lower()
    if host not in NOTIFY_HOSTS:
        raise NotifyError(f"push refused: {host} is not a notify host")


def _ntfy_priority(level: str) -> int:
    return {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}.get(level, 3)


def _pushover_priority(level: str) -> int:
    return {"min": -2, "low": -1, "default": 0, "high": 1, "urgent": 1}.get(level, 0)


def _redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "<redacted>") if secret else text
