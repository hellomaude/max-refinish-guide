"""The daemon: the cadence as a clock, and the pushes as conditions."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from desk.daemon import Paths, load_cadence, parse_cadence, run_forever, run_slot
from desk.loader import ValidationError
from desk.notify import Dedup, Push, deliver
from desk.sources import Health

ROOT = Path(__file__).resolve().parent.parent
LA = ZoneInfo("America/Los_Angeles")


def cadence_doc(**overrides):
    doc = {
        "schema_version": 1,
        "timezone": "America/Los_Angeles",
        "slots": [
            {"id": "morning", "days": ["mon", "tue", "wed", "thu", "fri"], "at": "06:30",
             "steps": ["stamp", "pack"]},
        ],
        "push": {"cooldown_hours": 4},
    }
    doc.update(overrides)
    return doc


class CadenceTests(unittest.TestCase):
    def test_the_shipped_cadence_loads(self):
        cadence = load_cadence(ROOT / "codex-feed" / "CADENCE.yaml")
        self.assertGreaterEqual(len(cadence.slots), 5)
        self.assertEqual(cadence.slot("morning").at, "06:30")

    def test_next_slot_respects_days_and_local_time(self):
        cadence = parse_cadence(cadence_doc())
        # Saturday 2026-09-19 10:00 LA -> next is Monday 06:30 LA
        now = datetime(2026, 9, 19, 10, 0, tzinfo=LA).astimezone(timezone.utc)
        slot, when = cadence.next_slot(now)
        self.assertEqual(slot.id, "morning")
        self.assertEqual(when.astimezone(LA), datetime(2026, 9, 21, 6, 30, tzinfo=LA))

    def test_a_slot_at_the_exact_minute_fires_next_week_not_now(self):
        cadence = parse_cadence(cadence_doc())
        now = datetime(2026, 9, 21, 6, 30, tzinfo=LA).astimezone(timezone.utc)
        _, when = cadence.next_slot(now)
        self.assertGreater(when, now)

    def test_the_daemon_may_not_fetch_or_confirm(self):
        with self.assertRaises(ValidationError) as caught:
            parse_cadence(cadence_doc(slots=[{"id": "x", "days": ["mon"], "at": "06:30",
                                              "steps": ["fetch"]}]))
        self.assertIn("steps must be from", str(caught.exception))

    def test_bad_time_is_refused(self):
        with self.assertRaises(ValidationError):
            parse_cadence(cadence_doc(slots=[{"id": "x", "days": ["mon"], "at": "25:00",
                                              "steps": ["stamp"]}]))

    def test_run_forever_sleeps_to_the_slot_then_runs(self):
        with _desk_copy() as root:
            paths = Paths(root)
            slept: list[float] = []
            clock_values = iter([
                datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),   # before 06:30 LA (13:30Z)
                datetime(2026, 9, 21, 13, 30, tzinfo=timezone.utc),  # at the slot
            ])
            ran = run_forever(paths, dry_run_push=True, sleep=slept.append,
                              clock=lambda: next(clock_values), max_sessions=1)
            self.assertEqual(ran, 1)
            self.assertEqual(len(slept), 1)
            self.assertAlmostEqual(slept[0], 5400.0)
            self.assertTrue(paths.log.exists())


class _desk_copy:
    """A throwaway copy of the shipped desk so a session can write."""

    def __enter__(self) -> Path:
        self.tmp = tempfile.mkdtemp()
        root = Path(self.tmp) / "desk"
        shutil.copytree(ROOT / "codex-feed", root / "codex-feed")
        shutil.copytree(ROOT / "tickets", root / "tickets")
        shutil.copytree(ROOT / "challenges", root / "challenges")
        (root / "reports").mkdir()
        return root

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


def _fake_probe(sources):
    return [Health(source_id=s.id, state="ok", status_code=200, latency_ms=10.0) for s in sources]


def _dark_probe(sources):
    out = []
    for s in sources:
        state = "unreachable" if s.id == "cboe_delayed_chain" else "ok"
        out.append(Health(source_id=s.id, state=state, status_code=None if state != "ok" else 200,
                          latency_ms=None, detail="CONNECT refused" if state != "ok" else ""))
    return out


class SessionTests(unittest.TestCase):
    NOW = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)

    def test_a_morning_slot_writes_every_artefact(self):
        with _desk_copy() as root:
            paths = Paths(root)
            cadence = load_cadence(paths.cadence)
            result = run_slot(cadence.slot("morning"), paths, cadence, now=self.NOW,
                              dry_run_push=True, probe=_fake_probe)
            self.assertTrue(result.ok, result.steps)
            self.assertTrue(list(paths.preflight.glob("*.json")))
            self.assertTrue(list(paths.assignments.glob("*.assignment.yaml")))
            self.assertTrue(list(paths.stamps.glob("*.json")))
            self.assertTrue(list(paths.packs.glob("*.md")))
            self.assertTrue(paths.last_stamp.exists())
            self.assertTrue(paths.log.exists())

    def test_a_dark_source_pushes_once(self):
        """Exactly one push per condition per cooldown — the dedup rule."""
        with _desk_copy() as root:
            paths = Paths(root)
            cadence = load_cadence(paths.cadence)
            first = run_slot(cadence.slot("morning"), paths, cadence, now=self.NOW,
                             dry_run_push=True, probe=_dark_probe)
            sent = [p for p, o in first.pushes if p.key.startswith("source:cboe") and o == "dry-run"]
            self.assertEqual(len(sent), 1)
            second = run_slot(cadence.slot("morning"), paths, cadence,
                              now=self.NOW + timedelta(hours=1), dry_run_push=True, probe=_dark_probe)
            again = [o for p, o in second.pushes if p.key.startswith("source:cboe")]
            self.assertEqual(again, ["suppressed"])

    def test_a_required_seat_dark_pushes(self):
        with _desk_copy() as root:
            paths = Paths(root)
            cadence = load_cadence(paths.cadence)
            result = run_slot(cadence.slot("open"), paths, cadence, now=self.NOW, dry_run_push=True)
            keys = [p.key for p, _ in result.pushes]
            self.assertIn("seat-dark:Rails", keys)

    def test_a_failed_step_is_logged_and_pushed_not_swallowed(self):
        with _desk_copy() as root:
            paths = Paths(root)
            # Break the book: a ticket the contract refuses.
            (paths.tickets / "broken.ticket.yaml").write_text("schema_version: 2\nid: BAD\n", encoding="utf-8")
            cadence = load_cadence(paths.cadence)
            result = run_slot(cadence.slot("open"), paths, cadence, now=self.NOW, dry_run_push=True)
            self.assertFalse(result.ok)
            self.assertEqual(result.steps[0][0], "load")
            self.assertIn("broken.ticket.yaml", result.steps[0][1])
            self.assertTrue(any(p.key.startswith("step-failed:") for p, _ in result.pushes))
            self.assertIn("failed", paths.log.read_text(encoding="utf-8"))


class DedupTests(unittest.TestCase):
    def test_cooldown_then_again(self):
        now = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            dedup = Dedup(Path(tmp) / "push.json", cooldown=timedelta(hours=4))
            push = Push(key="k", title="t", message="m")
            first = deliver([push], dedup, now=now, dry_run=True)
            self.assertEqual(first[0][1], "dry-run")
            second = deliver([push], dedup, now=now + timedelta(hours=1), dry_run=True)
            self.assertEqual(second[0][1], "suppressed")
            third = deliver([push], dedup, now=now + timedelta(hours=5), dry_run=True)
            self.assertEqual(third[0][1], "dry-run")

    def test_state_survives_a_restart(self):
        now = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "push.json"
            Dedup(path).mark("k", now=now)
            self.assertFalse(Dedup(path).should_send("k", now=now + timedelta(hours=1)))

    def test_unconfigured_is_not_marked_as_sent(self):
        """No service means nothing went out; do not suppress the next one."""
        import os

        now = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)
        saved = {k: os.environ.pop(k, None) for k in ("NTFY_TOPIC", "PUSHOVER_TOKEN", "PUSHOVER_USER")}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dedup = Dedup(Path(tmp) / "push.json")
                out = deliver([Push(key="k", title="t", message="m")], dedup, now=now)
                self.assertEqual(out[0][1], "unconfigured")
                self.assertTrue(dedup.should_send("k", now=now))
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
