"""Holdout governance and research budgets.

Partitions the timeline into development / validation / locked-test (and an
optional forward) window, and enforces a research budget per search family. The
locked test is gated: accessing it is recorded, and repeated access raises a
warning or (past a hard cap) blocks.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DataSplit:
    train_end: pd.Timestamp
    valid_end: pd.Timestamp
    # locked test is (valid_end, end]; optional forward beyond `test_end`.
    test_end: pd.Timestamp | None = None

    def mask(self, index: pd.DatetimeIndex, part: str) -> pd.Series:
        idx = pd.Series(index, index=index)
        if part == "train":
            return idx <= self.train_end
        if part == "valid":
            return (idx > self.train_end) & (idx <= self.valid_end)
        if part == "test":
            upper = self.test_end if self.test_end is not None else index[-1]
            return (idx > self.valid_end) & (idx <= upper)
        if part == "forward":
            if self.test_end is None:
                return idx > index[-1]  # empty
            return idx > self.test_end
        raise ValueError(f"unknown partition {part!r}")


def split_by_fraction(index: pd.DatetimeIndex, train: float = 0.6, valid: float = 0.2) -> DataSplit:
    n = len(index)
    return DataSplit(train_end=index[int(n * train) - 1], valid_end=index[int(n * (train + valid)) - 1])


@dataclass
class ResearchBudget:
    max_candidates: int = 200
    max_holdout_access: int = 3
    max_mutations_per_lineage: int = 10


class BudgetExceeded(RuntimeError):
    pass


class HoldoutGovernor:
    """Wraps a registry to enforce budgets and gate the locked test."""

    def __init__(self, registry, family: str, budget: ResearchBudget = ResearchBudget()):
        self.registry = registry
        self.family = family
        self.budget = budget

    def check_candidate_budget(self) -> None:
        used = self.registry.family_trial_count(self.family)
        if used >= self.budget.max_candidates:
            raise BudgetExceeded(
                f"family {self.family!r} exhausted candidate budget ({used}/{self.budget.max_candidates})"
            )

    def access_locked_test(self, experiment_id: str | None, reason: str, hard: bool = True) -> list[str]:
        """Record a locked-test access; return warnings. Blocks past the cap when
        ``hard`` is True."""
        prior = self.registry.holdout_access_count(self.family)
        warnings: list[str] = []
        if prior >= self.budget.max_holdout_access:
            msg = (
                f"locked-test access #{prior + 1} for family {self.family!r} exceeds cap "
                f"({self.budget.max_holdout_access}); results are no longer untouched validation"
            )
            if hard:
                raise BudgetExceeded(msg)
            warnings.append(msg)
        elif prior > 0:
            warnings.append(
                f"locked test already viewed {prior} time(s) for family {self.family!r}; "
                "further tuning against it inflates selection bias"
            )
        self.registry.record_holdout_access(self.family, experiment_id, reason)
        return warnings
