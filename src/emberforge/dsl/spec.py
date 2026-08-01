"""The declarative, validated factor specification.

A :class:`FactorSpec` is the unit of research currency. It carries the immutable
expression plus every piece of metadata required to reproduce, classify, and
audit it. Construction runs the full parse -> validate -> canonicalize -> hash
pipeline, so an invalid factor can never exist as a ``FactorSpec``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import canonical, causality, parser
from .nodes import Node, fields_used

Frequency = Literal["daily", "5Min", "1Min", "hourly", "weekly"]


def _max_lookback(node: Node) -> int:
    """Upper bound on how many prior bars the expression needs."""
    from .nodes import Call, Const

    total = 0
    for child in getattr(node, "args", ()):  # type: ignore[arg-type]
        total = max(total, _max_lookback(child))
    if isinstance(node, Call):
        from . import operators

        spec = operators.REGISTRY.get(node.op)
        if spec is not None:
            for idx in spec.window_args:
                arg = node.args[idx]
                if isinstance(arg, Const):
                    total += int(arg.value)
    return total


class FactorSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor_id: str
    expression: str
    description: str = ""
    economic_hypothesis: str = ""
    intended_frequency: Frequency = "daily"
    expected_sign: Literal[1, -1, 0] = 0
    generator: str = "manual"
    parent_ids: tuple[str, ...] = ()
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Derived / validated fields (populated in the model validator).
    canonical_expression: str = ""
    expression_hash: str = ""
    required_fields: tuple[str, ...] = ()
    max_lookback: int = 0
    complexity_score: int = 0

    @field_validator("factor_id")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("factor_id must be non-empty")
        return v

    @model_validator(mode="after")
    def _compile(self) -> "FactorSpec":
        tree: Node = parser.parse(self.expression)
        causality.validate(tree)
        derived = {
            "canonical_expression": canonical.canonical_string(tree),
            "expression_hash": canonical.factor_hash(tree),
            "required_fields": tuple(sorted(fields_used(tree))),
            "max_lookback": _max_lookback(tree),
            "complexity_score": causality.complexity_score(tree),
        }
        # Bypass frozen to set derived fields once, at construction.
        for key, value in derived.items():
            object.__setattr__(self, key, value)
        return self

    def tree(self) -> Node:
        return parser.parse(self.expression)


def make_factor(factor_id: str, expression: str, **kwargs) -> FactorSpec:
    """Convenience constructor that surfaces domain exceptions directly.

    Validating before pydantic construction means callers see ``ParseError`` /
    ``ValidationError`` / ``CausalityError`` rather than a wrapped pydantic error.
    """
    tree = parser.parse(expression)          # ParseError
    causality.validate(tree)                 # ValidationError / CausalityError
    return FactorSpec(factor_id=factor_id, expression=expression, **kwargs)
