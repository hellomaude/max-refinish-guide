"""The execution boundary, enforced rather than promised.

Doctrine says research seats never place orders, move funds, or connect a
wallet. Doctrine in a markdown file is a hope. This test is the mechanism:
it fails the build if order-placing machinery appears anywhere in the package,
and if the shipped policy quietly arms a venue.

If a future change needs one of these, the change must delete the rule here
deliberately — which is a diff a reviewer will see.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "desk"

# Substrings that have no business in a research package. Kept as plain text
# rather than imports because the point is to catch code that does not exist
# yet.
FORBIDDEN_CALLS = (
    "create_order",
    "place_order",
    "submit_order",
    "post_order",
    "cancel_order",
    "SecureClient",
    "eth_sendTransaction",
    "sign_typed_data",
    "signTypedData",
    "private_key",
    "PRIVATE_KEY",
    "mnemonic",
    "seed_phrase",
    "withdraw",
)

# PUT, PATCH and DELETE are banned outright, everywhere, with no allowlist.
FORBIDDEN_METHODS = ("PUT", "PATCH", "DELETE")

# POST is a different case. The invariant the desk wants is "no mutating
# request", not "no POST" — Hyperliquid's read endpoint takes a POST body, and
# refusing the verb outright would mean either losing the only funding source
# that works from this box, or writing the verb obliquely to dodge the check.
# So POST is confined to one module and the payloads it may send are pinned
# below. Widening either is a visible diff.
POST_ALLOWED_FILES = {"desk/adapters/base.py"}


def _python_files() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


class ExecutionBoundaryTests(unittest.TestCase):
    def test_no_order_placing_machinery_in_the_package(self):
        offenders: list[str] = []
        for path in _python_files():
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_CALLS:
                for i, line in enumerate(text.splitlines(), start=1):
                    # A comment explaining that we must NOT do a thing is fine.
                    stripped = line.strip()
                    if needle in line and not stripped.startswith("#"):
                        offenders.append(f"{path.relative_to(ROOT)}:{i}: {needle}")
        self.assertEqual(offenders, [], "order-placing machinery in a research package")

    def test_post_is_confined_to_the_allowlisted_module(self):
        offenders: list[str] = []
        for path in _python_files():
            relative = str(path.relative_to(ROOT))
            if relative in POST_ALLOWED_FILES:
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if '"POST"' in line or "'POST'" in line:
                    offenders.append(f"{relative}:{i}")
        self.assertEqual(offenders, [], "POST outside the allowlisted module")

    def test_read_only_request_payloads_are_pinned(self):
        """Every body an adapter sends must come from its declared read set."""
        from desk.adapters import hyperliquid

        self.assertEqual(
            hyperliquid.READ_ONLY_REQUESTS,
            ("metaAndAssetCtxs", "meta", "allMids", "fundingHistory"),
            "the Hyperliquid read allowlist changed; confirm every entry is a read",
        )
        source = (PACKAGE / "adapters" / "hyperliquid.py").read_text(encoding="utf-8")
        # The only body construction in the module must index that tuple.
        for i, line in enumerate(source.splitlines(), start=1):
            if "body=" in line:
                self.assertIn(
                    "READ_ONLY_REQUESTS", line,
                    f"desk/adapters/hyperliquid.py:{i} sends a body not drawn from the read allowlist",
                )

    def test_the_http_layer_only_reads(self):
        """No module may issue a mutating HTTP request."""
        offenders: list[str] = []
        for path in _python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in FORBIDDEN_METHODS:
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {node.value!r}")
                if isinstance(node, ast.keyword) and node.arg in ("data", "method"):
                    if isinstance(node.value, ast.Constant) and node.value.value in FORBIDDEN_METHODS:
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: {node.arg}={node.value.value!r}"
                        )
        self.assertEqual(offenders, [], "mutating HTTP in a read-only data layer")

    def test_source_registry_holds_no_credentials(self):
        """Keys live in the environment. A literal in the registry is a leak."""
        text = (ROOT / "codex-feed" / "sources.yaml").read_text(encoding="utf-8")
        suspicious = re.findall(
            r"(?im)^\s*(?:api[_-]?key|secret|token|password|private[_-]?key)\s*:\s*\S+", text
        )
        self.assertEqual(suspicious, [], "credential literal in sources.yaml")

    def test_adapter_endpoints_are_https(self):
        import re as _re

        for path in _python_files():
            for url in _re.findall(r"[\"']((?:http|ftp)[^\"'\s]*)[\"']", path.read_text(encoding="utf-8")):
                self.assertTrue(
                    url.startswith("https://"),
                    f"{path.relative_to(ROOT)} references a non-https endpoint: {url}",
                )

    def test_registry_urls_are_https(self):
        from desk.sources import load_sources

        for source in load_sources(ROOT / "codex-feed" / "sources.yaml"):
            self.assertTrue(
                source.url.startswith("https://"),
                f"{source.id} is not https",
            )

    def test_shipped_policy_arms_no_live_venue(self):
        from desk.mode import load_mode

        mode = load_mode(ROOT / "codex-feed" / "MODE.yaml")
        live = [v.id for v in mode.venues.values() if v.live]
        self.assertEqual(live, [], "a venue is marked live while the desk is research-only")

    def test_shipped_policy_keeps_execution_on_research_packs(self):
        """Moving off research_packs_only is a deliberate act, not a drift.

        If Max arms a broker, this assertion is the thing that has to change,
        and changing it shows up in review.
        """
        from desk.mode import load_mode

        mode = load_mode(ROOT / "codex-feed" / "MODE.yaml")
        self.assertEqual(mode.execution, "research_packs_only")

    def test_every_ticket_carries_the_max_gate(self):
        from desk.ticket import load_tickets

        tickets = load_tickets(ROOT / "tickets")
        for ticket in tickets:
            self.assertTrue(ticket.max_gate, f"{ticket.id} does not require Max's gate")


if __name__ == "__main__":
    unittest.main()
