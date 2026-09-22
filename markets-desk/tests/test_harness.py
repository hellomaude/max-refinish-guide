"""The harness: what an agent finds when it opens the package cold.

AGENTS.md read natively, CLAUDE.md pointing at it, a compact state file, and
paste-ready prompts with a slot for the input. If any of these go missing an agent
starts without the rules, which is how a boundary gets crossed politely.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PresenceTests(unittest.TestCase):
    def test_every_agent_entry_point_exists(self):
        for name in ("AGENTS.md", "CLAUDE.md", "GOAL.md", "HANDOFF.md", "HANDOFF-NATIVE.md", "HANDOFF-LOCAL.md",
                     ".motif/STATE.md", "prompts/README.md"):
            self.assertTrue((ROOT / name).exists(), f"{name} missing")

    def test_claude_points_at_agents(self):
        self.assertIn("AGENTS.md", (ROOT / "CLAUDE.md").read_text())

    def test_agents_carries_the_gate_and_the_bans(self):
        text = (ROOT / "AGENTS.md").read_text()
        for needle in ("test_boundary.py", "live: true", "research_packs_only",
                       "python -m desk validate", "Do not merge"):
            self.assertIn(needle, text)


class PromptTests(unittest.TestCase):
    PASTE = "<PASTE"

    def _prompts(self):
        return sorted(p for p in (ROOT / "prompts").glob("*_PROMPT.md"))

    def test_there_are_prompts(self):
        self.assertGreaterEqual(len(self._prompts()), 5)

    def test_every_prompt_has_a_paste_slot(self):
        for path in self._prompts():
            self.assertIn(self.PASTE, path.read_text(), f"{path.name} has no paste slot")

    def test_every_filing_prompt_demands_a_model_field(self):
        """The adversary rule bites on `model:`; a prompt that omits it
        produces files the rule cannot see."""
        for name in ("RESEARCH_SEAT_PROMPT.md", "JEV_PROMPT.md", "TICKET_PROMPT.md"):
            self.assertIn("model:", (ROOT / "prompts" / name).read_text(), name)

    def test_jev_prompt_forbids_adding_conviction(self):
        text = (ROOT / "prompts" / "JEV_PROMPT.md").read_text()
        self.assertIn("never positive", text)
        self.assertIn("self-review", text)

    def test_no_prompt_asks_for_an_order(self):
        for path in self._prompts():
            lower = path.read_text().lower()
            for banned in ("place the order", "execute the trade", "submit_order", "create_order"):
                self.assertNotIn(banned, lower, f"{path.name} contains {banned!r}")


class NativeHandoffTests(unittest.TestCase):
    """The native handoff must not quietly become an auto-trader spec."""

    def _text(self) -> str:
        return (ROOT / "HANDOFF-NATIVE.md").read_text()

    def test_it_defines_the_agent_as_window_gate_alarm(self):
        for needle in ("The window", "The gate", "The alarm"):
            self.assertIn(needle, self._text())

    def test_the_confirm_contract_requires_pass_hash_and_max(self):
        text = self._text()
        for needle in ("verdict: pass", "stamp_sha256", "confirmed_by: max", "expires_at"):
            self.assertIn(needle, text)

    def test_one_mutating_route(self):
        self.assertIn("one mutating route", self._text())

    def test_the_phone_holds_nothing_dangerous(self):
        self.assertIn("never holds a model, a key, a broker credential, or the pack", self._text())

    def test_it_never_promises_auto_trading(self):
        lower = self._text().lower()
        for banned in ("auto-execute", "executes automatically", "places the order for you",
                       "no confirmation needed"):
            self.assertNotIn(banned, lower)


class GoalTests(unittest.TestCase):
    """The goal must stay checkable and must never tick its own boxes."""

    def _text(self) -> str:
        return (ROOT / "GOAL.md").read_text()

    def test_every_done_condition_is_unticked(self):
        """Ticks are Max's. An agent that ticks its own goal has no goal."""
        self.assertNotIn("- [x]", self._text())
        self.assertGreaterEqual(self._text().count("- [ ]"), 20)

    def test_the_gate_is_named_as_never(self):
        text = self._text()
        for needle in ("Never set any venue `live: true`", "Never name a broker",
                       "Never merge, publish, or mark a PR ready"):
            self.assertIn(needle, text)

    def test_the_last_condition_pins_the_policy(self):
        self.assertIn("still has every venue `live: false`", self._text())

    def test_stop_conditions_exclude_silence_on_the_gate(self):
        self.assertIn("silence here. Ever.", self._text())


class StateTests(unittest.TestCase):
    def test_state_has_the_fields_max_reads(self):
        text = (ROOT / ".motif" / "STATE.md").read_text()
        for field in ("Idea:", "Track:", "Stage:", "Decisions:", "Artifacts:"):
            self.assertIn(field, text)

    def test_state_does_not_claim_a_live_venue(self):
        text = (ROOT / ".motif" / "STATE.md").read_text()
        self.assertIn("live:false", text.replace(" ", ""))


class LocalHandoffTests(unittest.TestCase):
    def _text(self) -> str:
        return (ROOT / "HANDOFF-LOCAL.md").read_text()

    def test_it_is_for_the_mac_and_starts_with_the_launcher(self):
        text = self._text()
        self.assertIn("launch-mac.sh", text)
        self.assertLess(text.index("L0"), text.index("L1"))

    def test_it_never_asks_to_edit_policy_to_get_a_pass(self):
        text = self._text()
        self.assertIn("Never** edit the real `MODE.yaml`", text)
        self.assertIn("temporary copy", text)

    def test_it_keeps_the_swift_guard_rules(self):
        text = self._text()
        for needle in ('httpMethod = "POST"', "SecItem", "AgeLabel"):
            self.assertIn(needle, text)


class LauncherTests(unittest.TestCase):
    """The one command that stands the desk up on a Mac."""

    def _text(self) -> str:
        return (ROOT / "install" / "launch-mac.sh").read_text()

    def test_it_exists_and_is_executable(self):
        import os

        path = ROOT / "install" / "launch-mac.sh"
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))

    def test_it_runs_the_gate_before_anything_starts(self):
        text = self._text()
        self.assertLess(text.index("unittest discover"), text.index("install-macos.sh"))
        self.assertIn("set -euo pipefail", text)

    def test_it_never_touches_policy(self):
        text = self._text()
        self.assertNotIn("MODE.yaml", text.replace("never edits MODE.yaml", ""))
        self.assertNotIn("live: true", text)
        self.assertNotIn("sed -i", text)

    def test_it_degrades_to_the_served_page_without_xcode(self):
        text = self._text()
        self.assertIn("xcode-select -p", text)
        self.assertIn("served page is the UI until it is", text)
