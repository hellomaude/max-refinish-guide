"""The roster: which model sits in which seat, and the rules that keep a
multi-model desk from becoming a multi-model echo.

A seat is anything that satisfies a contract. That makes the desk
model-agnostic, which is the easy half. The hard half is that once several
frontier models are on the desk, the natural thing to do — have them vote —
is exactly wrong. Their errors correlate through shared training data and
shared sources, so agreement is cheap and disagreement is a tie with no
tiebreak. The roster therefore assigns models to seats by *capability the
desk would otherwise lack*, and enforces one rule with teeth: the adversary
must be a different model from the proposer. A challenge filed by the
ticket's own model is self-review and does not count.

Tickets, challenges and reports may carry an optional `model` field. When a
filing names a model it must be one the roster knows; when it names none, the
seat's roster assignment is assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .challenge import Challenge
from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant
from .ticket import Ticket

ANY_MODEL = "any"

# Seats that are not research seats for the concentration rule.
NON_RESEARCH = ("Codex", "Jev")


HOSTINGS = ("local", "api")


@dataclass(frozen=True)
class ModelSpec:
    id: str
    vendor: str
    strengths: str
    hosting: str = "api"
    license: str = ""
    web: bool = False

    @property
    def is_local(self) -> bool:
        return self.hosting == "local"


@dataclass(frozen=True)
class SeatAssignment:
    seat: str
    model: str
    why: str
    pool: tuple[str, ...] = ()
    fallback: str = ""


@dataclass(frozen=True)
class Roster:
    updated_at: datetime
    models: Mapping[str, ModelSpec]
    seats: Mapping[str, SeatAssignment]
    adversary_must_differ: bool = True
    adversary_pool_needs_local: bool = True
    score_by_model: bool = True
    max_research_seats_per_model: int = 6
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def leaves_box(self, seat: str) -> bool | None:
        """Whether what this seat reads is sent off the desk machine.

        None when the seat is unassigned or `any`. The dashboard and
        `validate` use this to say which filings a hosted vendor sees.
        """
        model = self.model_for(seat)
        if model is None or model == ANY_MODEL:
            return None
        spec = self.models.get(model)
        return None if spec is None else not spec.is_local

    def local_models(self) -> tuple[str, ...]:
        return tuple(m for m, spec in self.models.items() if spec.is_local)

    def web_models(self) -> tuple[str, ...]:
        """Models a chat window can stand in for. A local model is never one."""
        return tuple(m for m, spec in self.models.items() if spec.web and not spec.is_local)

    def adversary_pool(self) -> tuple[str, ...]:
        jev = self.seats.get("Jev")
        return jev.pool if jev else ()

    def model_for(self, seat: str) -> str | None:
        found = self._seat(seat)
        return found.model if found else None

    def knows_model(self, model: str) -> bool:
        return model.strip().lower() in self.models or model.strip().lower() == ANY_MODEL

    def _seat(self, seat: str) -> SeatAssignment | None:
        needle = seat.strip().lower()
        for name, assignment in self.seats.items():
            if name.strip().lower() == needle:
                return assignment
        return None

    def proposer_models(self, ticket: Ticket) -> set[str]:
        """The model(s) behind a ticket: its own `model` if declared, else the
        roster assignment of every seat in `source_seats`."""
        declared = str(ticket.raw.get("model", "")).strip().lower()
        if declared:
            return {declared}
        out: set[str] = set()
        for seat in ticket.source_seats:
            found = self.model_for(seat)
            if found and found != ANY_MODEL:
                out.add(found)
        return out

    def challenger_model(self, challenge: Challenge) -> str | None:
        declared = str(challenge.raw.get("model", "")).strip().lower()
        if declared:
            return declared
        found = self.model_for(challenge.challenger)
        return None if found in (None, ANY_MODEL) else found

    def is_independent(self, ticket: Ticket, challenge: Challenge) -> bool:
        """Whether this challenge came from a different model than the ticket.

        Unknown on either side is treated as independent: the rule bites on
        what is declared, not on what is missing. A desk that wants the rule
        to bite harder declares `model` on every filing.
        """
        if not self.adversary_must_differ:
            return True
        who = self.challenger_model(challenge)
        if who is None:
            return True
        return who not in self.proposer_models(ticket)

    def independent_challenges(
        self, tickets: Iterable[Ticket], challenges: Mapping[str, Challenge]
    ) -> tuple[dict[str, Challenge], list[str]]:
        """Split challenges into those that count and the reasons for those
        that do not. A self-review leaves its ticket unchallenged."""
        by_id = {t.id: t for t in tickets}
        kept: dict[str, Challenge] = {}
        dropped: list[str] = []
        for ticket_id, challenge in challenges.items():
            ticket = by_id.get(ticket_id)
            if ticket is None or self.is_independent(ticket, challenge):
                kept[ticket_id] = challenge
                continue
            who = self.challenger_model(challenge)
            dropped.append(
                f"{ticket_id}: challenge by {challenge.challenger} ({who}) is the "
                f"proposer's own model — self-review does not count; ticket stays "
                "unchallenged until a different model argues against it"
            )
        return kept, dropped

    def concentration(self) -> dict[str, int]:
        """Research seats per model."""
        counts: dict[str, int] = {}
        for seat, assignment in self.seats.items():
            if seat in NON_RESEARCH or assignment.model == ANY_MODEL:
                continue
            counts[assignment.model] = counts.get(assignment.model, 0) + 1
        return counts

    def problems(self) -> list[str]:
        """Rule violations in the roster itself."""
        out: list[str] = []
        for model, count in self.concentration().items():
            if count > self.max_research_seats_per_model:
                out.append(
                    f"roster: {model} holds {count} research seats, over the cap of "
                    f"{self.max_research_seats_per_model} — one vendor's blind spot "
                    "would be the desk's"
                )
        jev = self.seats.get("Jev")
        if jev is not None and jev.model != ANY_MODEL:
            out.append(
                "roster: Jev is pinned to one model. The adversary must be whichever "
                "model did not write the ticket, or the rule cannot hold"
            )
        if jev is not None and self.adversary_pool_needs_local:
            local = [m for m in jev.pool if m in self.models and self.models[m].is_local]
            if not local:
                out.append(
                    "roster: Jev's pool has no local model — every frontier-authored "
                    "ticket would have to leave the box to be challenged"
                )
        for model, spec in self.models.items():
            if spec.web and spec.is_local:
                out.append(
                    f"roster: {model} is both local and web — a chat window is not on the box"
                )
        for seat, assignment in self.seats.items():
            for member in assignment.pool:
                if member not in self.models:
                    out.append(f"roster: seats.{seat}.pool names undeclared model {member!r}")
            if assignment.fallback and assignment.fallback not in self.models:
                out.append(
                    f"roster: seats.{seat}.fallback names undeclared model "
                    f"{assignment.fallback!r}"
                )
        return out


_SPECS = (
    FieldSpec("schema_version", int, minimum=1, maximum=1),
    FieldSpec("updated_at", (str, datetime)),
    FieldSpec("models", dict),
    FieldSpec("seats", dict),
    FieldSpec("rules", dict, required=False),
)


def parse_roster(doc: Mapping[str, Any], *, where: str = "roster") -> Roster:
    problems = check_fields(doc, _SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    extra: list[str] = []
    models: dict[str, ModelSpec] = {}
    for model_id, spec in (doc["models"] or {}).items():
        if not isinstance(spec, dict):
            extra.append(f"models.{model_id}: expected a mapping")
            continue
        hosting = str(spec.get("hosting", "api")).strip().lower()
        if hosting not in HOSTINGS:
            extra.append(f"models.{model_id}: hosting {hosting!r} not one of {list(HOSTINGS)}")
            continue
        models[str(model_id).lower()] = ModelSpec(
            id=str(model_id).lower(),
            vendor=str(spec.get("vendor", "")),
            strengths=str(spec.get("strengths", "")).strip(),
            hosting=hosting,
            license=str(spec.get("license", "")),
            web=bool(spec.get("web", False)),
        )

    seats: dict[str, SeatAssignment] = {}
    for seat, spec in (doc["seats"] or {}).items():
        if not isinstance(spec, dict) or "model" not in spec:
            extra.append(f"seats.{seat}: needs a `model`")
            continue
        model = str(spec["model"]).strip().lower()
        if model != ANY_MODEL and model not in models:
            extra.append(f"seats.{seat}: model {model!r} is not declared under `models`")
            continue
        if not str(spec.get("why", "")).strip():
            extra.append(
                f"seats.{seat}: needs a `why` — an assignment with no capability behind "
                "it is a second vote"
            )
            continue
        pool = tuple(str(m).strip().lower() for m in (spec.get("pool") or ()))
        seats[str(seat)] = SeatAssignment(
            seat=str(seat),
            model=model,
            why=str(spec["why"]).strip(),
            pool=pool,
            fallback=str(spec.get("fallback", "")).strip().lower(),
        )

    rules = doc.get("rules") or {}
    roster = Roster(
        updated_at=parse_instant(doc["updated_at"], field="updated_at"),
        models=models,
        seats=seats,
        adversary_must_differ=bool(rules.get("adversary_must_differ", True)),
        adversary_pool_needs_local=bool(rules.get("adversary_pool_needs_local", True)),
        score_by_model=bool(rules.get("score_by_model", True)),
        max_research_seats_per_model=int(rules.get("max_research_seats_per_model", 6)),
        raw=doc,
    )
    extra.extend(roster.problems())
    if extra:
        raise ValidationError(extra, where=where)
    return roster


def load_roster(path: str | Path) -> Roster:
    return parse_roster(load_document(path), where=str(path))


def check_filings(
    roster: Roster,
    tickets: Iterable[Ticket],
    challenges: Mapping[str, Challenge],
) -> list[str]:
    """Problems with the `model` declared on filings, for `desk validate`."""
    out: list[str] = []
    for ticket in tickets:
        declared = str(ticket.raw.get("model", "")).strip()
        if declared and not roster.knows_model(declared):
            out.append(f"{ticket.id}: model {declared!r} is not in the roster")
        for seat in ticket.source_seats:
            if roster.model_for(seat) is None:
                out.append(f"{ticket.id}: seat {seat!r} has no roster assignment")
    for ticket_id, challenge in challenges.items():
        declared = str(challenge.raw.get("model", "")).strip()
        if declared and not roster.knows_model(declared):
            out.append(f"{ticket_id}: challenge model {declared!r} is not in the roster")
    return out
