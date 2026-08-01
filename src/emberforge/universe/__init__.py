"""Point-in-time universe membership as a first-class research input.

A universe is a time-by-symbol boolean *eligibility* mask. The critical property
is **point-in-time correctness**: membership observed at timestamp ``t`` may only
affect evaluation from the next permissible timestamp (``t+1``), never earlier.
Emberforge enforces this by lagging membership one bar before it is applied, so a
symbol entering/leaving the index at ``t`` cannot retroactively change ``t``.

Four kinds are distinguished:

* ``static``               — every symbol eligible at every time (the trivial case);
* ``point_in_time``        — membership genuinely changes over time (PIT);
* ``survivorship_stressed``— symbols that "die" are removed *only after* death,
  and also removed going forward, stressing survivorship assumptions;
* ``research_only``        — an explicit approximation, flagged as not PIT-clean.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

import pandas as pd

UniverseKind = Literal["static", "point_in_time", "survivorship_stressed", "research_only"]


@dataclass(frozen=True)
class Universe:
    name: str
    kind: UniverseKind
    membership: pd.DataFrame  # index=timestamp, columns=symbol, bool
    fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "membership", self.membership.astype(bool).sort_index())
        object.__setattr__(self, "fingerprint", self._fingerprint())

    def _fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(f"{self.name}|{self.kind}".encode())
        h.update(pd.util.hash_pandas_object(self.membership, index=True).values.tobytes())
        return h.hexdigest()[:32]

    def eligibility(self, index: pd.DatetimeIndex, columns) -> pd.DataFrame:
        """Return the PIT-safe eligibility mask aligned to ``index``/``columns``.

        Membership is shifted forward one bar: what we *knew* at t-1 governs what
        is eligible at t. The first bar has no prior knowledge and is ineligible.
        """
        m = self.membership.reindex(index=index, columns=columns).fillna(False)
        return m.shift(1).fillna(False).astype(bool)

    def apply(self, scores: pd.DataFrame) -> pd.DataFrame:
        """Mask a score matrix to eligible (t, symbol) cells, PIT-safely."""
        elig = self.eligibility(scores.index, scores.columns)
        return scores.where(elig)


def static_universe(index: pd.DatetimeIndex, symbols, name: str = "static") -> Universe:
    membership = pd.DataFrame(True, index=index, columns=list(symbols))
    return Universe(name=name, kind="static", membership=membership)


def point_in_time_universe(
    membership: pd.DataFrame, name: str = "pit"
) -> Universe:
    return Universe(name=name, kind="point_in_time", membership=membership)


def survivorship_stressed(
    membership: pd.DataFrame, death_dates: dict[str, pd.Timestamp], name: str = "survivorship"
) -> Universe:
    """Zero out membership for each symbol on/after its death date."""
    m = membership.copy().astype(bool)
    for sym, dt in death_dates.items():
        if sym in m.columns:
            m.loc[m.index >= pd.Timestamp(dt), sym] = False
    return Universe(name=name, kind="survivorship_stressed", membership=m)


def research_only(membership: pd.DataFrame, name: str = "research_only") -> Universe:
    """An explicit approximation — labelled so it is never mistaken for PIT-clean."""
    return Universe(name=name, kind="research_only", membership=membership)


__all__ = [
    "Universe", "UniverseKind",
    "static_universe", "point_in_time_universe", "survivorship_stressed", "research_only",
]
