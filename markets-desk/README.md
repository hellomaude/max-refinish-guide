# Max Motif Markets Desk

Research plumbing for the markets desk described in `HANDOFF-CLAUDE.md`. It turns
seat research into tickets, applies Rails' caps deterministically, and scores what
the desk actually got right.

**It does not trade.** Nothing here places an order, moves funds, signs a
transaction, or connects a wallet. Every allowance it produces is a ceiling for
Codex to work inside, and Max gates every order. See `codex-feed/DOCTRINE.md`.

## Why this exists

The desk it replaces worked, but three things were carried by hand:

- **Caps lived in prose.** Rails re-read `MODE.md` and re-derived sizing every
  session, so the same book could be stamped two ways on two days.
- **Freshness was a checklist item.** An options feed frozen at Friday's expiry
  was caught by a human noticing, not by anything refusing to use it.
- **Nothing was scored.** Tickets were proposed, stamped, and forgotten, so
  "confidence 4" never had to mean anything.

Each is now a mechanism: `MODE.yaml`, the staleness gate, and the ledger.

## Layout

```
codex-feed/MODE.yaml     desk policy — modes, caps, themes, event windows, freshness
codex-feed/sources.yaml  every upstream, who owns it, what to fall back to
desk/                    the implementation (stdlib only, plus PyYAML)
tickets/*.ticket.yaml    the book
ledger/*.outcome.yaml    what happened, for scoring
```

## Use

```bash
python -m desk validate     # refuse a malformed book before Codex sees it
python -m desk preflight    # probe every source; name what is dark and why
python -m desk stamp        # Rails over the whole book at once
python -m desk pack --out … # render the Codex pack
python -m desk score        # realised hit rate, expectancy and calibration
```

`stamp` runs over the whole book deliberately. A ticket's allowance depends on
what else competes for the same theme cap, so tickets cannot be sized one at a
time and added together — that is how a 0.5% idea becomes 1.5% of one factor.

## The two rules worth knowing

**Correlated ideas share a cap.** `crypto_policy_beta` holds COIN, HOOD, MSTR,
MARA, spot BTC/ETH, the ETFs and the US crypto-policy prediction markets under a
single 1.5%. September 15 settled the argument: one Senate cloture vote moved
every leg at once.

**A single-name override is a one-member theme.** SBLK's 0.75% and RWT's 0.25%
are themes with one member, not a second mechanism.

## Docs

- [`docs/CONNECTORS.md`](docs/CONNECTORS.md) — which connectors to keep, add, drop, and what no connector fixes
- [`docs/RISK-MODEL.md`](docs/RISK-MODEL.md) — units, theme caps, the conviction ladder, water-filling
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module map and failure posture
- [`docs/MIGRATION.md`](docs/MIGRATION.md) — moving the Grok Bot desk onto this, in order
- [`codex-feed/DOCTRINE.md`](codex-feed/DOCTRINE.md) — roles, bans, and what is enforced rather than promised

## Tests

```bash
pip install pyyaml
python -m unittest discover -s tests -t .
```

81 tests, no network. `tests/test_boundary.py` is the one that matters most: it
fails the build if order-placing machinery, signing material or a mutating HTTP
verb appears in the package, or if the shipped policy arms a venue. Lifting a
ban means deleting an assertion, which shows up in review.

## Status

Working and tested: policy, ticket contract, Rails engine, source registry and
prober, ledger, CLI, CI. Still to come: per-seat source adapters that turn the
registry into fetched evidence, and the equity-venue decision in
[`docs/MIGRATION.md`](docs/MIGRATION.md).

The 18 registered sources are written against documented APIs but **unverified** —
this session's egress blocked every market-data host. Run `python -m desk
preflight` on the desk box before any seat relies on them.
