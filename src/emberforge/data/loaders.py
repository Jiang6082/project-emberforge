"""Provider-neutral loaders: local CSV/Parquet and a read-only Geld adapter.

The Geld adapter opens Geld's SQLite database in **read-only** mode (SQLite URI
``mode=ro``) and maps its 5-minute ``market_bars`` rows into an Emberforge panel.
It imports nothing from ``geld.*`` and writes nothing anywhere under the Geld
tree — the boundary is one-way and offline. It is not exercised by the test
suite (which must run with no external data).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .schema import DatasetMetadata, MarketData


def load_csv_dir(path: str | Path, frequency: str = "daily", source: str = "local_csv") -> MarketData:
    """Load one CSV per field from ``path`` (e.g. ``close.csv``). Each CSV has a
    timestamp index column and one column per symbol."""
    path = Path(path)
    panels: dict[str, pd.DataFrame] = {}
    for field in ("open", "high", "low", "close", "volume", "vwap"):
        f = path / f"{field}.csv"
        if f.exists():
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            panels[field] = df
    if "close" not in panels:
        raise FileNotFoundError(f"no close.csv found under {path}")
    return MarketData(panels, DatasetMetadata(source=source, frequency=frequency, feed="local"))


def load_parquet(path: str | Path, source: str = "local_parquet") -> MarketData:
    """Load a long-form parquet with columns [timestamp, symbol, field, value]."""
    df = pd.read_parquet(path)
    panels = {
        field: sub.pivot(index="timestamp", columns="symbol", values="value")
        for field, sub in df.groupby("field")
    }
    return MarketData(panels, DatasetMetadata(source=source, feed="local"))


def load_geld_bars(
    sqlite_path: str | Path,
    timeframe: str = "5Min",
    symbols: list[str] | None = None,
) -> MarketData:
    """Read Geld's cached bars **read-only** and map them to an Emberforge panel.

    Mapping: Geld ``Bar(symbol, timestamp, open, high, low, close, volume,
    timeframe)`` -> Emberforge OHLCV panels (vwap approximated as (H+L+C)/3, since
    Geld stores none). Adjustment/feed/version are marked unknown because Geld
    does not record them.
    """
    uri = f"file:{Path(sqlite_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        query = "SELECT symbol, timestamp, open, high, low, close, volume FROM market_bars WHERE timeframe = ?"
        params: list = [timeframe]
        if symbols:
            placeholders = ",".join("?" for _ in symbols)
            query += f" AND symbol IN ({placeholders})"
            params.extend(symbols)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    if not rows:
        raise ValueError(f"no {timeframe} bars found in {sqlite_path}")
    frame = pd.DataFrame(rows, columns=["symbol", "timestamp", "open", "high", "low", "close", "volume"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    panels = {
        field: frame.pivot(index="timestamp", columns="symbol", values=field)
        for field in ("open", "high", "low", "close", "volume")
    }
    panels["vwap"] = (panels["high"] + panels["low"] + panels["close"]) / 3.0
    meta = DatasetMetadata(
        source="project_geld_readonly", frequency=timeframe, feed="alpaca(unknown)",
        adjustment="unknown", version="geld-cache",
    )
    return MarketData(panels, meta)
