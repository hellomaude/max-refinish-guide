"""`python -m desk` — the desk's command line.

Nine verbs, each one a thing a seat or Codex actually does:
    validate   refuse a malformed book before it reaches Codex
    preflight  probe the data layer and say what is reachable
    fetch      pull a seat's evidence, ready to paste into a ticket
    assign     issue a research seat its work order, and audit what came back
    challenge  list what Jev has not argued against yet
    stamp      run Rails over the book and print allowances
    pack       render the Codex pack for a session
    score      report how the desk's past ideas actually did
    coach      grade a research seat's calls and say what to change
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .assign import audit, build_assignment, load_assignments, render_assignment
from .challenge import load_challenges, unchallenged
from .coach import coach, coverage_history, grade_crowding, grade_report, level_counts
from .report import load_report_history, load_reports, seats_reporting
from .roster import check_filings, load_roster
from .ledger import (
    calibration_report,
    challenge_report,
    load_outcomes,
    score as score_outcomes,
    write_csv,
)
from .loader import DeskError, ValidationError
from .mode import load_mode
from .risk import Book, OpenRisk, stamp_book
from .sources import load_sources, probe_all, write_report
from .ticket import load_tickets

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODE = ROOT / "codex-feed" / "MODE.yaml"
DEFAULT_TICKETS = ROOT / "tickets"
DEFAULT_SOURCES = ROOT / "codex-feed" / "sources.yaml"
DEFAULT_OUTCOMES = ROOT / "ledger"
DEFAULT_CHALLENGES = ROOT / "challenges"
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_ASSIGNMENTS = ROOT / "assignments"
DEFAULT_ROSTER = ROOT / "codex-feed" / "ROSTER.yaml"


def _now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    raw = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise SystemExit("--now needs an explicit timezone offset")
    return parsed.astimezone(timezone.utc)


def _counted_challenges(args: argparse.Namespace, tickets) -> dict:
    """Challenges that count: self-reviews are dropped and said so.

    A challenge filed by the proposer's own model leaves its ticket
    unchallenged. Every verb that gates on Jev goes through here so the rule
    cannot be bypassed by picking a different command.
    """
    challenges = load_challenges(args.challenges)
    roster_path = Path(getattr(args, "roster", DEFAULT_ROSTER))
    if not roster_path.exists():
        return challenges
    roster = load_roster(roster_path)
    kept, dropped = roster.independent_challenges(tickets, challenges)
    for line in dropped:
        print(f"SELF-REVIEW {line}", file=sys.stderr)
    return kept


def _open_risk(path: str | None) -> OpenRisk:
    if not path:
        return OpenRisk()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return OpenRisk(by_theme=data.get("by_theme", {}), by_symbol=data.get("by_symbol", {}))


def cmd_validate(args: argparse.Namespace) -> int:
    problems: list[str] = []
    try:
        mode = load_mode(args.mode)
        print(f"mode      ok   {mode.mode} / {mode.execution} (updated {mode.updated_at:%Y-%m-%d})")
    except (DeskError, OSError) as exc:
        problems.append(f"mode: {exc}")
        mode = None
    try:
        tickets = load_tickets(args.tickets)
        print(f"tickets   ok   {len(tickets)} loaded from {args.tickets}")
    except (DeskError, OSError) as exc:
        problems.append(f"tickets: {exc}")
        tickets = []
    try:
        sources = load_sources(args.sources)
        print(f"sources   ok   {len(sources)} registered")
    except (DeskError, OSError) as exc:
        problems.append(f"sources: {exc}")

    try:
        challenges = load_challenges(args.challenges)
        print(f"challenge ok   {len(challenges)} on record")
    except (DeskError, OSError) as exc:
        problems.append(f"challenges: {exc}")
        challenges = {}

    roster = None
    if Path(args.roster).exists():
        try:
            roster = load_roster(args.roster)
            counts = ", ".join(f"{m} {n}" for m, n in sorted(roster.concentration().items()))
            print(f"roster    ok   {len(roster.seats)} seats ({counts})")
            problems.extend(check_filings(roster, tickets, challenges))
            kept, dropped = roster.independent_challenges(tickets, challenges)
            for line in dropped:
                print(f"SELF-REVIEW {line}", file=sys.stderr)
            challenges = kept
        except (DeskError, OSError) as exc:
            problems.append(f"roster: {exc}")

    try:
        reports = load_reports(args.reports)
        filed = seats_reporting(reports)
        print(f"reports   ok   {len(reports)} filed, {len(filed)} with a read")
        for name, report in sorted(reports.items()):
            if report.unavailable:
                print(f"DARK      {name}: {', '.join(report.unavailable)}", file=sys.stderr)
    except (DeskError, OSError) as exc:
        problems.append(f"reports: {exc}")
        reports = {}

    if mode is not None:
        missing = [s for s in mode.required_seats if s not in seats_reporting(reports)]
        for seat in missing:
            print(f"PENDING   required seat has not filed: {seat}", file=sys.stderr)

    if mode is not None and mode.require_challenge:
        missing = unchallenged([t.id for t in tickets], challenges)
        for ticket_id in missing:
            print(f"PENDING   {ticket_id}: awaiting Jev", file=sys.stderr)

    if mode is not None:
        for ticket in tickets:
            if mode.theme_for(ticket.instrument.label()) is None and mode.theme_by_id(ticket.theme) is None:
                problems.append(
                    f"{ticket.id}: theme {ticket.theme!r} is not defined in MODE.yaml and "
                    f"{ticket.instrument.label()!r} matches no theme membership"
                )

    for problem in problems:
        print(f"FAIL      {problem}", file=sys.stderr)
    return 1 if problems else 0


def cmd_preflight(args: argparse.Namespace) -> int:
    sources = load_sources(args.sources)
    if args.seat:
        sources = [s for s in sources if s.seat.lower() == args.seat.lower()]
    health = probe_all(sources, timeout=args.timeout)
    width = max((len(h.source_id) for h in health), default=10)
    for entry in health:
        latency = "" if entry.latency_ms is None else f"{entry.latency_ms:6.0f}ms"
        print(f"{entry.source_id:<{width}}  {entry.state:<12} {latency:>8}  {entry.detail}")
    if args.out:
        path = write_report(health, args.out)
        print(f"\nwrote {path}")
    broken = [h for h in health if not h.usable]
    if broken:
        print(f"\n{len(broken)} of {len(health)} sources unusable", file=sys.stderr)
    return 1 if broken and args.strict else 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """Run one seat's adapters and print evidence in ticket form.

    Output is deliberately paste-ready YAML rather than a report: the seat's
    job is to put these lines into a ticket, and retyping a number is how a
    wrong one gets in.
    """
    from .adapters import cboe, edgar, fred, hyperliquid, polymarket

    seat = args.seat.lower()
    results = []
    if seat == "odds":
        if not args.slug:
            raise SystemExit("--slug is required for the Odds seat")
        results.append(polymarket.fetch_market(args.slug, outcome=args.outcome))
    elif seat == "chain":
        result = hyperliquid.fetch_funding_oi(args.coin or ["BTC", "ETH"])
        results.append(result)
        if result.ok and not args.quiet:
            for coin in args.coin or ["BTC", "ETH"]:
                print(f"# {hyperliquid.crowding_read(result, coin)}")
    elif seat == "pulse":
        result = cboe.fetch_gex(args.symbol or "_SPX")
        results.append(result)
        if result.ok and not args.quiet:
            print(f"# {cboe.positioning_read(result)}")
    elif seat == "shadow":
        if not args.cik:
            raise SystemExit("--cik is required for the Shadow seat")
        result = edgar.fetch_insider_cluster(args.cik, ticker=args.ticker or "")
        results.append(result)
        if result.ok and not args.quiet:
            print(f"# {edgar.cluster_read(result, args.ticker or f'CIK {args.cik}')}")
    elif seat == "ledger":
        for name in args.series or ["10y", "2s10s"]:
            results.append(fred.fetch_named(name))
    else:
        raise SystemExit(f"no adapters registered for seat {args.seat!r}")

    failures = [r for r in results if not r.ok]
    rows = [row for r in results if r.ok for row in r.as_ticket_evidence()]
    if rows:
        print("evidence:")
        for row in rows:
            print(f"  - key: {row['key']}")
            print(f"    kind: {row['kind']}")
            print(f"    value: {json.dumps(row['value'])}")
            print(f"    source: {row['source']}")
            print(f"    as_of: {row['as_of']}")
            if row.get("url"):
                print(f"    url: {row['url']}")
    for result in results:
        if result.error:
            print(f"# {result.source_id}: {result.error}", file=sys.stderr)
    return 1 if failures else 0


def cmd_challenge(args: argparse.Namespace) -> int:
    """What the adversary still owes the desk."""
    tickets = load_tickets(args.tickets)
    challenges = _counted_challenges(args, tickets)
    pending = unchallenged([t.id for t in tickets], challenges)

    for ticket in tickets:
        for _, report in sorted(reports.items()):
            level = report.crowding_for(ticket.instrument.symbol)
            if level:
                out += [f"- **{report.seat} crowding:** {level}", ""]
        held = challenges.get(ticket.id)
        if held:
            print(held.line())
        else:
            print(f"{ticket.id}: UNCHALLENGED — {ticket.instrument.label()} ({ticket.direction})")
    if pending:
        print(f"\n{len(pending)} ticket(s) awaiting Jev: {', '.join(pending)}", file=sys.stderr)
    return 1 if pending else 0


def _render_book(book: Book) -> str:
    lines = [
        f"# Rails stamp — {book.stamped_at:%Y-%m-%d %H:%M UTC}",
        "",
        f"mode `{book.mode}` · execution `{book.execution}` · "
        f"allocated {book.portfolio_allowed_pct:.2f}% of a {book.portfolio_cap_pct:.2f}% heat cap",
        "",
        "| ticket | verdict | Jev | asked | allowed | binding constraint |",
        "|---|---|---|---:|---:|---|",
    ]
    for stamp in book.ranked():
        jev = stamp.challenge_verdict or "—"
        lines.append(
            f"| {stamp.ticket_id} | {stamp.verdict.upper()} | {jev} | {stamp.requested_pct:.2f}% "
            f"| **{stamp.allowed_pct:.2f}%** | {stamp.binding_constraint} |"
        )
    lines.append("")
    for stamp in book.ranked():
        if not (stamp.reasons or stamp.stale_evidence or stamp.missing_seats):
            continue
        lines.append(f"**{stamp.ticket_id}**")
        for reason in stamp.reasons:
            lines.append(f"- {reason}")
        for item in stamp.stale_evidence:
            lines.append(f"- stale: {item}")
        for seat in stamp.missing_seats:
            lines.append(f"- waiting on seat: {seat}")
        lines.append("")
    lines.append("Every allowance above is a ceiling, not an instruction. Max gates each order.")
    return "\n".join(lines)


def cmd_stamp(args: argparse.Namespace) -> int:
    mode = load_mode(args.mode)
    tickets = load_tickets(args.tickets)
    book = stamp_book(
        tickets,
        mode,
        now=_now(args.now),
        open_risk=_open_risk(args.open_risk),
        available_seats=args.seat or (seats_reporting(load_reports(args.reports)) or None),
        challenges=_counted_challenges(args, tickets),
    )
    if args.json:
        payload = {
            "stamped_at": book.stamped_at.isoformat(),
            "mode": book.mode,
            "execution": book.execution,
            "portfolio_allowed_pct": round(book.portfolio_allowed_pct, 2),
            "portfolio_cap_pct": book.portfolio_cap_pct,
            "stamps": [
                {
                    "ticket_id": s.ticket_id,
                    "verdict": s.verdict,
                    "requested_pct": s.requested_pct,
                    "allowed_pct": s.allowed_pct,
                    "theme": s.theme,
                    "binding_constraint": s.binding_constraint,
                    "reasons": s.reasons,
                    "stale_evidence": s.stale_evidence,
                    "missing_seats": s.missing_seats,
                }
                for s in book.ranked()
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(_render_book(book))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    mode = load_mode(args.mode)
    tickets = load_tickets(args.tickets)
    now = _now(args.now)
    challenges = _counted_challenges(args, tickets)
    reports = load_reports(args.reports)
    book = stamp_book(tickets, mode, now=now, open_risk=_open_risk(args.open_risk),
                      challenges=challenges,
                      available_seats=seats_reporting(reports) or None)
    by_id = {t.id: t for t in tickets}

    out = [
        f"# Codex pack — {now:%Y-%m-%d %H:%M UTC}",
        "",
        f"Desk is `{mode.mode}` / `{mode.execution}`. Research only; Max gates every order.",
        "",
        *(
            ["## Seat reads", ""]
            + [f"- {r.line()}" for _, r in sorted(reports.items())]
            + [""]
            if reports
            else []
        ),
        _render_book(book),
        "",
        "## Tickets",
        "",
    ]
    for stamp in book.ranked():
        ticket = by_id[stamp.ticket_id]
        out += [
            f"### {ticket.id} — {ticket.instrument.label()} ({ticket.direction})",
            "",
            f"- **Rails:** {stamp.verdict.upper()} at {stamp.allowed_pct:.2f}% "
            f"({stamp.binding_constraint})",
            f"- **Seats:** {', '.join(ticket.source_seats)} · confidence {ticket.confidence}/5 "
            f"· horizon {ticket.horizon}",
            f"- **Thesis:** {ticket.thesis}",
            f"- **Catalyst:** {ticket.catalyst}",
            f"- **Invalidation:** {ticket.invalidation}",
            "",
        ]
        for _, report in sorted(reports.items()):
            level = report.crowding_for(ticket.instrument.symbol)
            if level:
                out += [f"- **{report.seat} crowding:** {level}", ""]
        held = challenges.get(ticket.id)
        if held:
            out += [
                f"**Jev ({held.verdict}, conviction {held.confidence_adjustment:+d}):** "
                f"{held.strongest_counter}",
                "",
                f"*Would change its mind:* {held.what_would_change_my_mind}",
                "",
            ]
            if held.missed_invalidation:
                out += [f"*Invalidation the author missed:* {held.missed_invalidation}", ""]
        if ticket.evidence:
            out.append("| evidence | value | source | as of |")
            out.append("|---|---|---|---|")
            for item in ticket.evidence:
                out.append(
                    f"| {item.key} | {item.value} | {item.source} | {item.as_of:%Y-%m-%d %H:%MZ} |"
                )
            out.append("")
    text = "\n".join(out)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {path}")
    else:
        print(text)
    return 0


def cmd_assign(args: argparse.Namespace) -> int:
    mode = load_mode(args.mode)
    tickets = load_tickets(args.tickets) if Path(args.tickets).exists() else []
    now = _now(args.now)
    reports = load_reports(args.reports) if Path(args.reports).exists() else {}

    if args.audit:
        existing = load_assignments(args.assignments)
        held = existing.get(args.seat)
        if held is None:
            print(f"no assignment on file for {args.seat} under {args.assignments}")
            return 1
        coverage = audit(held, reports.get(args.seat), now=now)
        print(f"assignment issued {held.issued_at:%Y-%m-%d %H:%MZ}, up to "
              f"{held.at_stake_pct:.2f}% of book risk waiting on it")
        for line in coverage.lines():
            print(line)
        return 0 if coverage.complete or not args.strict else 1

    assignment = build_assignment(
        args.seat,
        tickets,
        mode,
        now=now,
        prior=reports.get(args.seat),
        note=args.note or "",
    )
    if not assignment.tasks:
        print(
            f"nothing to assign {args.seat}: every name in the book already carries a "
            "call inside the freshness budget"
        )
        return 0

    print(f"# {args.seat} — {len(assignment.tasks)} task(s), up to "
          f"{assignment.at_stake_pct:.2f}% of book risk waiting on the answers")
    for task in assignment.tasks:
        print(task.line())

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_assignment(assignment), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


def cmd_coach(args: argparse.Namespace) -> int:
    tickets = load_tickets(args.tickets) if Path(args.tickets).exists() else []
    outcomes = load_outcomes(args.outcomes, tickets) if Path(args.outcomes).exists() else []
    history = load_report_history(args.reports) if Path(args.reports).exists() else []
    now = _now(args.now)

    mine = [r for r in history if r.seat.strip().lower() == args.seat.strip().lower()]
    if not mine:
        print(f"no reports from {args.seat} under {args.reports}; nothing to grade yet")
        return 0

    counts = level_counts(history, seat=args.seat)
    total = sum(counts.values())
    print(f"## {args.seat}: {len(mine)} report(s), {total} crowding call(s)")
    for level, count in counts.items():
        share = f"{count / total:.0%}" if total else "  - "
        print(f"  {level:<16} {count:>4}  {share:>5}")
    if total and counts["crowded"] == 0:
        print(
            "  note: `crowded` never used — a level that never fires is not caution, "
            "it is an unused field"
        )

    grade = grade_crowding(outcomes, history, tickets, seat=args.seat)
    print()
    for line in grade_report(grade):
        print(line)

    coverage = coverage_history(
        load_assignments(args.assignments), history, now=now, seat=args.seat
    )
    if coverage:
        print()
        for entry in coverage:
            for line in entry.lines():
                print(line)

    print(f"\n## what to change")
    for line in coach(grade, coverage, seat=args.seat):
        print(f"- {line}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    tickets = load_tickets(args.tickets) if Path(args.tickets).exists() else []
    outcomes = load_outcomes(args.outcomes, tickets) if Path(args.outcomes).exists() else []
    if not outcomes:
        print(f"no outcomes recorded under {args.outcomes}; nothing to score yet")
        return 0
    seat_to_model = None
    if Path(args.roster).exists():
        roster = load_roster(args.roster)
        if roster.score_by_model:
            seat_to_model = {s: a.model for s, a in roster.seats.items()}
    dimensions = ("seat", "theme", "confidence") + (("model",) if seat_to_model else ())
    for dimension in dimensions:
        rows = score_outcomes(outcomes, dimension=dimension, seat_to_model=seat_to_model)
        print(f"\n## by {dimension}")
        print(f"{'key':<18} {'prop':>5} {'taken':>6} {'res':>5} {'hit':>6} {'E[R]':>7} {'ΣR':>7}")
        for entry in rows:
            hit = "  -  " if entry.hit_rate is None else f"{entry.hit_rate:5.0%}"
            exp = "   -   " if entry.expectancy_r is None else f"{entry.expectancy_r:+6.2f}"
            print(
                f"{entry.key:<18} {entry.proposed:>5} {entry.taken:>6} {entry.resolved:>5} "
                f"{hit:>6} {exp:>7} {entry.total_r:>+7.2f}"
            )
    print()
    for line in calibration_report(outcomes):
        print(line)
    print()
    for line in challenge_report(outcomes, load_challenges(args.challenges)):
        print(line)
    if args.csv:
        write_csv(score_outcomes(outcomes, dimension="seat"), args.csv)
        print(f"\nwrote {args.csv}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="desk", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--mode", default=str(DEFAULT_MODE))
        p.add_argument("--tickets", default=str(DEFAULT_TICKETS))
        p.add_argument("--challenges", default=str(DEFAULT_CHALLENGES))
        p.add_argument("--reports", default=str(DEFAULT_REPORTS))
        p.add_argument("--roster", default=str(DEFAULT_ROSTER))

    p_validate = sub.add_parser("validate", help="structurally check mode, tickets and sources")
    common(p_validate)
    p_validate.add_argument("--sources", default=str(DEFAULT_SOURCES))
    p_validate.set_defaults(func=cmd_validate)

    p_challenge = sub.add_parser("challenge", help="list tickets Jev has not argued against")
    common(p_challenge)
    p_challenge.set_defaults(func=cmd_challenge)

    p_pre = sub.add_parser("preflight", help="probe every registered data source")
    p_pre.add_argument("--sources", default=str(DEFAULT_SOURCES))
    p_pre.add_argument("--seat", help="only probe sources belonging to one seat")
    p_pre.add_argument("--timeout", type=float, default=12.0)
    p_pre.add_argument("--out", help="write a JSON health report here")
    p_pre.add_argument("--strict", action="store_true", help="exit non-zero if any source is unusable")
    p_pre.set_defaults(func=cmd_preflight)

    p_fetch = sub.add_parser("fetch", help="pull a seat's evidence, ready to paste into a ticket")
    p_fetch.add_argument("seat", help="Odds | Chain | Pulse | Shadow | Ledger")
    p_fetch.add_argument("--slug", help="Odds: Polymarket market slug")
    p_fetch.add_argument("--outcome", help="Odds: restrict to one outcome, e.g. No")
    p_fetch.add_argument("--coin", action="append", help="Chain: perp symbol (repeatable)")
    p_fetch.add_argument("--symbol", help="Pulse: CBOE chain symbol, default _SPX")
    p_fetch.add_argument("--cik", type=int, help="Shadow: SEC CIK")
    p_fetch.add_argument("--ticker", help="Shadow: label for the evidence keys")
    p_fetch.add_argument("--series", action="append", help="Ledger: FRED series or shorthand")
    p_fetch.add_argument("--quiet", action="store_true", help="evidence only, no read line")
    p_fetch.set_defaults(func=cmd_fetch)

    p_assign = sub.add_parser("assign", help="issue a research seat its work order")
    common(p_assign)
    p_assign.add_argument("seat", help="the seat to assign, e.g. Grok")
    p_assign.add_argument("--assignments", default=str(DEFAULT_ASSIGNMENTS))
    p_assign.add_argument("--now", help="ISO-8601 instant to issue as of (default: now)")
    p_assign.add_argument("--out", help="write the assignment YAML here")
    p_assign.add_argument("--note", help="one line of context for the seat")
    p_assign.add_argument(
        "--audit",
        action="store_true",
        help="instead of issuing, check the filed report against the standing assignment",
    )
    p_assign.add_argument(
        "--strict", action="store_true", help="--audit: exit non-zero if anything is unanswered"
    )
    p_assign.set_defaults(func=cmd_assign)

    p_stamp = sub.add_parser("stamp", help="run Rails over the book")
    common(p_stamp)
    p_stamp.add_argument("--now", help="ISO-8601 instant to stamp as of (default: now)")
    p_stamp.add_argument("--open-risk", help="JSON file of risk already deployed")
    p_stamp.add_argument("--seat", action="append", help="seat report available (repeatable)")
    p_stamp.add_argument("--json", action="store_true")
    p_stamp.set_defaults(func=cmd_stamp)

    p_pack = sub.add_parser("pack", help="render the Codex pack")
    common(p_pack)
    p_pack.add_argument("--now")
    p_pack.add_argument("--open-risk")
    p_pack.add_argument("--out")
    p_pack.set_defaults(func=cmd_pack)

    p_score = sub.add_parser("score", help="report realised performance from the ledger")
    p_score.add_argument("--tickets", default=str(DEFAULT_TICKETS))
    p_score.add_argument("--outcomes", default=str(DEFAULT_OUTCOMES))
    p_score.add_argument("--challenges", default=str(DEFAULT_CHALLENGES))
    p_score.add_argument("--roster", default=str(DEFAULT_ROSTER))
    p_score.add_argument("--csv")
    p_score.set_defaults(func=cmd_score)

    p_coach = sub.add_parser("coach", help="grade a research seat and say what to change")
    p_coach.add_argument("seat", nargs="?", default="Grok")
    p_coach.add_argument("--tickets", default=str(DEFAULT_TICKETS))
    p_coach.add_argument("--outcomes", default=str(DEFAULT_OUTCOMES))
    p_coach.add_argument("--reports", default=str(DEFAULT_REPORTS))
    p_coach.add_argument("--assignments", default=str(DEFAULT_ASSIGNMENTS))
    p_coach.add_argument("--now")
    p_coach.set_defaults(func=cmd_coach)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValidationError as exc:
        print(f"validation failed — {exc}", file=sys.stderr)
        return 2
    except DeskError as exc:
        print(f"desk error — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
