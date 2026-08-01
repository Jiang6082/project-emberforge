"""Layer 1: syntactic deduplication via canonical hashes."""

from __future__ import annotations

from ..dsl.spec import FactorSpec


def is_syntactic_duplicate(a: FactorSpec, b: FactorSpec) -> bool:
    return a.expression_hash == b.expression_hash


def find_syntactic_duplicates(candidate: FactorSpec, existing: list[FactorSpec]) -> list[str]:
    return [e.factor_id for e in existing if is_syntactic_duplicate(candidate, e)]
