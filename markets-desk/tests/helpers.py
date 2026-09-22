"""Fixtures shared by the desk tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from desk.mode import parse_mode
from desk.ticket import parse_ticket

NOW = datetime(2026, 9, 21, 13, 30, tzinfo=timezone.utc)  # Monday 06:30 PT


def build_mode(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "mode": "live_confirm",
        "execution": "research_packs_only",
        "updated_at": "2026-09-20T09:00:00-07:00",
        "caps": {
            "portfolio_heat_pct": 3.0,
            "single_name_pct": 1.0,
            "default_theme_pct": 1.5,
        },
        "conviction_ladder": {1: 0.0, 2: 0.2, 3: 0.4, 4: 0.7, 5: 1.0},
        "themes": [
            {"id": "crypto_policy_beta", "cap_pct": 1.5,
             "members": ["COIN", "HOOD", "MSTR", "BTC", "clarity-act-*"]},
            {"id": "insider_shipping", "cap_pct": 0.75, "members": ["SBLK"]},
        ],
        "event_windows": [],
        "venues": {
            "equity": {"enabled": True, "live": False},
            "polymarket": {"enabled": True, "live": False},
            "option": {"enabled": False, "live": False, "note": "no options venue named"},
        },
        "staleness_hours": {"default": 72, "options_greeks": 20, "price": 24},
        "required_seats": [],
    }
    doc.update(overrides)
    return parse_mode(doc, where="test-mode")


def build_ticket(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "id": "T-001",
        "created_at": "2026-09-21T06:00:00-07:00",
        "source_seats": ["Chain"],
        "instrument": {"kind": "equity", "symbol": "COIN", "venue": "equity"},
        "direction": "long",
        "theme": "crypto_policy_beta",
        "thesis": "A thesis long enough to clear the minimum length the contract enforces.",
        "catalyst": "Monday cash open tape",
        "invalidation": "Loses the reclaim level on a closing basis.",
        "horizon": "intraday",
        "size_hint_pct": 1.0,
        "confidence": 5,
        "evidence": [
            {"key": "spot", "kind": "price", "value": 81300, "source": "Kraken",
             "as_of": "2026-09-21T06:00:00-07:00"},
        ],
        "sources": ["https://example.invalid/note"],
        "rails_check": "pass",
        "max_gate": True,
        "entry": 100.0,
        "stop": 95.0,
    }
    instrument = overrides.pop("instrument", None)
    if instrument:
        doc["instrument"] = {**doc["instrument"], **instrument}
    doc.update(overrides)
    return parse_ticket(doc, where=f"test-ticket:{doc['id']}")


def hours_ago(hours: float, *, base: datetime = NOW) -> str:
    return (base - timedelta(hours=hours)).isoformat()
