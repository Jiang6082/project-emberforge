"""Market-data container with explicit provenance metadata and a fingerprint.

Emberforge *introduces* rich data metadata (feed, adjustment, version, source,
fingerprint). Project Geld has none of this today — see
``docs/PROJECT_GELD_INTERFACE_NOTES.md``. A :class:`MarketData` panel is a dict
of ``field -> DataFrame(index=timestamp, columns=symbol)``.
"""

from __future__ import annotations

import hashlib
from typing import Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict

FIELDS = ("open", "high", "low", "close", "volume", "vwap")


class DatasetMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    frequency: str = "daily"
    timezone: str = "UTC"
    adjustment: str = "none"  # none | split | split_dividend
    feed: str = "synthetic"
    version: str = "v1"
    symbols: tuple[str, ...] = ()
    start: Optional[str] = None
    end: Optional[str] = None
    fingerprint: str = ""


class MarketData:
    """A causal, immutable-by-convention panel of market data."""

    def __init__(self, panels: dict[str, pd.DataFrame], metadata: DatasetMetadata):
        if "close" not in panels:
            raise ValueError("MarketData requires at least a 'close' panel")
        # Align every panel to a shared, sorted index and column order.
        index = panels["close"].index.sort_values()
        symbols = list(panels["close"].columns)
        self.panels = {
            name: df.reindex(index=index, columns=symbols).sort_index()
            for name, df in panels.items()
        }
        self.metadata = metadata.model_copy(
            update={
                "symbols": tuple(symbols),
                "start": str(index[0]),
                "end": str(index[-1]),
                "fingerprint": self._fingerprint(self.panels, metadata),
            }
        )

    @staticmethod
    def _fingerprint(panels: dict[str, pd.DataFrame], meta: DatasetMetadata) -> str:
        h = hashlib.sha256()
        h.update(f"{meta.source}|{meta.frequency}|{meta.feed}|{meta.version}".encode())
        for name in sorted(panels):
            df = panels[name]
            h.update(name.encode())
            h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
        return h.hexdigest()[:32]

    @property
    def symbols(self) -> list[str]:
        return list(self.panels["close"].columns)

    @property
    def index(self) -> pd.DatetimeIndex:
        return self.panels["close"].index

    def field(self, name: str) -> pd.DataFrame:
        if name == "returns":
            return self.panels["close"].pct_change()
        if name not in self.panels:
            raise KeyError(f"field {name!r} not available; have {sorted(self.panels)}")
        return self.panels[name]

    def has_field(self, name: str) -> bool:
        return name == "returns" or name in self.panels

    def forward_returns(self, horizon: int = 1) -> pd.DataFrame:
        """Return from t to t+horizon, aligned at t. This is the *label* and is
        never available to factor expressions (which only see fields at/<= t)."""
        close = self.panels["close"]
        return close.shift(-horizon) / close - 1.0
