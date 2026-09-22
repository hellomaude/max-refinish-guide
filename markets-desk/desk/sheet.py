"""The order sheet: the last artefact the desk produces, and the only one
that needs a confirm to exist.

A sheet is what Codex hands to a venue once one is armed. Until then it is a
paper sheet in `sheets/`, and the two-week paper run in `HANDOFF-NATIVE.md`
is built on comparing these to what Max would have done by hand.

The one rule: `format_sheet` takes a `Confirm` and refuses one that does not
match the book. There is no `format_sheet` without a confirm — not an
optional argument, not a `--force`. `tests/test_boundary.py` asserts the
signature, so removing the parameter is a visible diff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .confirm import Confirm
from .loader import ValidationError
from .mode import Mode
from .risk import Book, Stamp
from .ticket import Ticket


@dataclass(frozen=True)
class Sheet:
    ticket_id: str
    formatted_at: datetime
    paper: bool
    venue: str
    instrument: str
    direction: str
    allowed_pct: float
    risk_budget_usd: float | None
    risk_usd: float | None
    notional_usd: float | None
    entry: float | None
    stop: float | None
    confirm_sha256: str
    confirm_device: str
    note: str = ""

    def render(self) -> str:
        kind = "PAPER SHEET — no venue is live" if self.paper else "ORDER SHEET"
        lines = [
            f"# {kind}",
            "",
            f"ticket:        {self.ticket_id}",
            f"formatted_at:  {self.formatted_at:%Y-%m-%dT%H:%M:%S%z}",
            f"venue:         {self.venue or '(none named)'}",
            f"instrument:    {self.instrument}",
            f"direction:     {self.direction}",
            f"ceiling:       {self.allowed_pct:.2f}% of risk budget",
        ]
        if self.risk_budget_usd is not None:
            lines.append(f"risk_budget:   ${self.risk_budget_usd:,.2f}")
        if self.risk_usd is not None:
            lines.append(f"risk_at_stop:  ${self.risk_usd:,.2f}")
        if self.notional_usd is not None:
            lines.append(f"notional:      ${self.notional_usd:,.2f}")
        else:
            lines.append("notional:      (ticket lacks the price structure to size — kicked back)")
        lines.append(f"entry:         {self.entry if self.entry is not None else '—'}")
        lines.append(f"stop:          {self.stop if self.stop is not None else '—'}")
        lines.append("")
        lines.append(f"confirmed by max from {self.confirm_device}; stamp {self.confirm_sha256[:12]}…")
        if self.note:
            lines.append(f"note: {self.note}")
        lines.append("")
        lines.append("A ceiling, confirmed. Not an instruction to exceed it, and not an order")
        lines.append("until a venue is live and Max sends it.")
        return "\n".join(lines) + "\n"


def format_sheet(
    ticket: Ticket,
    stamp: Stamp,
    book: Book,
    mode: Mode,
    confirm: Confirm,
    *,
    now: datetime,
    risk_budget_usd: float | None = None,
) -> Sheet:
    """Turn a confirmed ceiling into a sheet, or refuse.

    Refuses when the confirm is for another ticket, expired, or made against
    a book that has since moved. Every refusal names the reason, because a
    sheet that was not written should never be a mystery.
    """
    if confirm.ticket_id != ticket.id:
        raise ValidationError([f"confirm is for {confirm.ticket_id}, sheet is for {ticket.id}"], where="sheet")
    problems = confirm.problems(stamp, book, now=now)
    if problems:
        raise ValidationError(problems, where="sheet")

    venue = mode.venue(ticket.instrument.venue) if ticket.instrument.venue else None
    paper = mode.execution == "research_packs_only" or venue is None or not venue.live

    risk_usd = None
    notional = None
    if risk_budget_usd is not None:
        risk_usd = round(stamp.allowed_pct / 100.0 * risk_budget_usd, 2)
        sized = ticket.notional_for_risk(risk_usd)
        notional = None if sized is None else round(sized, 2)

    return Sheet(
        ticket_id=ticket.id,
        formatted_at=now,
        paper=paper,
        venue=ticket.instrument.venue,
        instrument=ticket.instrument.label(),
        direction=ticket.direction,
        allowed_pct=stamp.allowed_pct,
        risk_budget_usd=risk_budget_usd,
        risk_usd=risk_usd,
        notional_usd=notional,
        entry=ticket.entry,
        stop=ticket.stop,
        confirm_sha256=confirm.stamp_sha256,
        confirm_device=confirm.device,
        note=confirm.note,
    )


def write_sheet(sheet: Sheet, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tag = "paper" if sheet.paper else "order"
    path = directory / f"{sheet.formatted_at:%Y-%m-%d-%H%M%S}-{sheet.ticket_id}.{tag}.sheet.md"
    path.write_text(sheet.render(), encoding="utf-8")
    return path
