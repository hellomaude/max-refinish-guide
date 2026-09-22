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
        for name in ("AGENTS.md", "CLAUDE.md", "HANDOFF.md", "HANDOFF-NATIVE.md",
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


class StateTests(unittest.TestCase):
    def test_state_has_the_fields_max_reads(self):
        text = (ROOT / ".motif" / "STATE.md").read_text()
        for field in ("Idea:", "Track:", "Stage:", "Decisions:", "Artifacts:"):
            self.assertIn(field, text)

    def test_state_does_not_claim_a_live_venue(self):
        text = (ROOT / ".motif" / "STATE.md").read_text()
        self.assertIn("live:false", text.replace(" ", ""))
