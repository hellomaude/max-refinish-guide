"""Loading + structural validation without third-party schema libraries.

The desk runs on a one-person box. Every dependency is a thing that can be
broken at 06:30 on a Monday, so validation here is hand-rolled and stdlib-only
(PyYAML is imported lazily, and only for .yaml inputs).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


class DeskError(Exception):
    """Base class for every error the desk raises on purpose."""


class ValidationError(DeskError):
    """A document did not satisfy its contract."""

    def __init__(self, problems: Iterable[str], *, where: str = "") -> None:
        self.problems = list(problems)
        self.where = where
        head = f"{where}: " if where else ""
        super().__init__(head + "; ".join(self.problems))


def load_document(path: str | Path) -> dict[str, Any]:
    """Load a .yaml/.yml/.json document into a dict."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - env dependent
            raise DeskError(
                f"{path} is YAML but PyYAML is not installed (pip install pyyaml)"
            ) from exc
        data = yaml.safe_load(text)
    elif path.suffix == ".json":
        data = json.loads(text)
    else:
        raise DeskError(f"{path}: unsupported extension {path.suffix!r}")
    if not isinstance(data, dict):
        raise DeskError(f"{path}: expected a mapping at the top level")
    return data


def parse_instant(value: Any, *, field: str) -> datetime:
    """Parse an ISO-8601 instant, requiring an explicit timezone.

    A naive timestamp is the classic way a desk convinces itself stale data is
    fresh, so the contract refuses them outright.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        raise ValidationError(
            [f"{field}: date-only value {value!r}; use a full timestamp with timezone"]
        )
    elif isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValidationError([f"{field}: {value!r} is not ISO-8601"]) from exc
    else:
        raise ValidationError([f"{field}: expected an ISO-8601 string, got {type(value).__name__}"])
    if parsed.tzinfo is None:
        raise ValidationError([f"{field}: {value!r} has no timezone offset"])
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class FieldSpec:
    """One field's contract."""

    name: str
    kind: type | tuple[type, ...]
    required: bool = True
    choices: tuple[Any, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    item_kind: type | tuple[type, ...] | None = None
    min_items: int = 0


def check_fields(doc: Mapping[str, Any], specs: Iterable[FieldSpec], *, where: str) -> list[str]:
    """Return a list of human-readable problems; empty means the doc is good."""
    problems: list[str] = []
    for spec in specs:
        if spec.name not in doc or doc[spec.name] is None:
            if spec.required:
                problems.append(f"missing required field {spec.name!r}")
            continue
        value = doc[spec.name]
        # bool is a subclass of int; a flag is never an acceptable number here.
        if spec.kind is not bool and isinstance(value, bool) and bool not in _as_tuple(spec.kind):
            problems.append(f"{spec.name}: expected {_kind_name(spec.kind)}, got bool")
            continue
        if not isinstance(value, spec.kind):
            problems.append(f"{spec.name}: expected {_kind_name(spec.kind)}, got {type(value).__name__}")
            continue
        if spec.choices is not None and value not in spec.choices:
            problems.append(f"{spec.name}: {value!r} not one of {list(spec.choices)}")
        if spec.minimum is not None and isinstance(value, (int, float)) and value < spec.minimum:
            problems.append(f"{spec.name}: {value} below minimum {spec.minimum}")
        if spec.maximum is not None and isinstance(value, (int, float)) and value > spec.maximum:
            problems.append(f"{spec.name}: {value} above maximum {spec.maximum}")
        if isinstance(value, list):
            if len(value) < spec.min_items:
                problems.append(f"{spec.name}: needs at least {spec.min_items} item(s)")
            if spec.item_kind is not None:
                for i, item in enumerate(value):
                    if not isinstance(item, spec.item_kind):
                        problems.append(
                            f"{spec.name}[{i}]: expected {_kind_name(spec.item_kind)}, "
                            f"got {type(item).__name__}"
                        )
    return problems


def _as_tuple(kind: type | tuple[type, ...]) -> tuple[type, ...]:
    return kind if isinstance(kind, tuple) else (kind,)


def _kind_name(kind: type | tuple[type, ...]) -> str:
    return " or ".join(k.__name__ for k in _as_tuple(kind))
