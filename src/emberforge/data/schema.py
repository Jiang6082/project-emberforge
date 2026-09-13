"""Market-data container with explicit provenance metadata and a fingerprint.

Metadata includes feed, adjustment, version, source and fingerprint. See
``docs/PROJECT_GELD_INTERFACE_NOTES.md`` for the current offline boundary.
A :class:`MarketData` panel is a dict
of ``field -> DataFrame(index=timestamp, columns=symbol)``.
"""

from __future__ import annotations

import hashlib
import json

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
    start: str | None = None
    end: str | None = None
    fingerprint: str = ""


class MarketData:
    """A causal, immutable-by-convention panel of market data."""

    def __init__(self, panels: dict[str, pd.DataFrame], metadata: DatasetMetadata):
        if "close" not in panels:
            raise ValueError("MarketData requires at least a 'close' panel")
        close = panels["close"]
        if close.empty or not isinstance(close.index, pd.DatetimeIndex):
            raise ValueError("MarketData requires a non-empty DatetimeIndex and symbol columns")
        for name, panel in panels.items():
            if panel.index.has_duplicates or panel.columns.has_duplicates or panel.index.hasnans:
                raise ValueError(f"{name}: timestamps and symbols must be unique and timestamps non-missing")
            if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in panel.dtypes):
                raise ValueError(f"{name}: values must be numeric")
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
        h.update(json.dumps(meta.model_dump(exclude={"fingerprint", "start", "end", "symbols"}),
                            sort_keys=True).encode())
        for name in sorted(panels):
            df = panels[name]
            h.update(name.encode())
            h.update(json.dumps([str(c) for c in df.columns]).encode())
            h.update(json.dumps([str(d) for d in df.dtypes]).encode())
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
            return self.panels["close"].pct_change(fill_method=None)
        if name not in self.panels:
            raise KeyError(f"field {name!r} not available; have {sorted(self.panels)}")
        return self.panels[name]

    def has_field(self, name: str) -> bool:
        return name == "returns" or name in self.panels

    def forward_returns(self, horizon: int = 1) -> pd.DataFrame:
        """Return from t to t+horizon, aligned at t. This is the *label* and is
        never available to factor expressions (which only see fields at/<= t)."""
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            raise ValueError("horizon must be a positive integer")
        close = self.panels["close"]
        return close.shift(-horizon) / close - 1.0

    def subset(self, mask: pd.Series) -> MarketData:
        """Return a new MarketData restricted to timestamps where ``mask`` is True.

        Used to evaluate on a development/validation window without ever exposing
        the locked test — the agent and robustness tools slice with this.
        """
        idx = self.index[mask.reindex(self.index, fill_value=False).values]
        panels = {name: df.loc[idx] for name, df in self.panels.items()}
        return MarketData(panels, self.metadata.model_copy(update={"fingerprint": ""}))

    def subset_by_date(self, start=None, end=None) -> MarketData:
        idx = self.index
        def aligned(value):
            timestamp = pd.Timestamp(value)
            if idx.tz is not None:
                return timestamp.tz_localize(idx.tz) if timestamp.tz is None else timestamp.tz_convert(idx.tz)
            if timestamp.tz is not None:
                raise ValueError("timezone-aware boundary requires a timezone-aware dataset")
            return timestamp
        mask = pd.Series(True, index=idx)
        if start is not None:
            mask &= idx >= aligned(start)
        if end is not None:
            mask &= idx <= aligned(end)
        return self.subset(mask)
