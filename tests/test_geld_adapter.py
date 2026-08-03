"""Integration test for the read-only Project Geld adapter.

Builds a database with Geld's *exact* ``market_bars`` schema in a temp dir (never
touching Geld's real file), then proves ``load_geld_bars`` round-trips it into a
usable ``MarketData`` and that the connection is genuinely read-only.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from emberforge.compute import compute_factor
from emberforge.data import load_geld_bars
from emberforge.dsl import make_factor

# Geld's schema, copied verbatim from geld/storage/database.py
_GELD_SCHEMA = """
CREATE TABLE market_bars (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, timestamp)
);
"""


def _make_geld_db(path, symbols=("SPY", "QQQ", "NVDA", "AAPL", "TSLA"), n_bars=80, timeframe="5Min"):
    conn = sqlite3.connect(path)
    conn.executescript(_GELD_SCHEMA)
    start = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    rows = []
    for si, sym in enumerate(symbols):
        price = 100.0 + 10 * si
        for k in range(n_bars):
            ts = (start + timedelta(minutes=5 * k)).isoformat()
            price *= 1 + ((k % 7) - 3) * 0.001  # deterministic wiggle
            o, c = price, price * 1.001
            rows.append((sym, timeframe, ts, o, max(o, c) * 1.002, min(o, c) * 0.998, c, 1_000_000 + 1000 * k))
    conn.executemany(
        "INSERT INTO market_bars (symbol, timeframe, timestamp, open, high, low, close, volume) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_adapter_loads_geld_schema(tmp_path):
    db = tmp_path / "geld.sqlite3"
    _make_geld_db(db)
    data = load_geld_bars(db, timeframe="5Min")

    assert set(data.symbols) == {"SPY", "QQQ", "NVDA", "AAPL", "TSLA"}
    for field in ("open", "high", "low", "close", "volume", "vwap"):
        assert data.has_field(field)
    assert data.metadata.source == "project_geld_readonly"
    assert data.metadata.frequency == "5Min"
    # vwap is synthesized as (H+L+C)/3 since Geld stores none
    assert data.metadata.fingerprint


def test_adapter_output_computes_a_factor(tmp_path):
    db = tmp_path / "geld.sqlite3"
    _make_geld_db(db)
    data = load_geld_bars(db, timeframe="5Min")
    scores = compute_factor(make_factor("m", "cs_rank(ts_returns(close, 5))"), data)
    assert scores.shape == (len(data.index), len(data.symbols))
    assert scores.notna().any().any()


def test_adapter_symbol_filter(tmp_path):
    db = tmp_path / "geld.sqlite3"
    _make_geld_db(db)
    data = load_geld_bars(db, timeframe="5Min", symbols=["SPY", "QQQ"])
    assert set(data.symbols) == {"SPY", "QQQ"}


def test_adapter_is_read_only(tmp_path):
    db = tmp_path / "geld.sqlite3"
    _make_geld_db(db)
    before = db.stat().st_mtime_ns, db.stat().st_size
    load_geld_bars(db, timeframe="5Min")
    after = db.stat().st_mtime_ns, db.stat().st_size
    assert before == after  # loading changed nothing on disk

    # a mode=ro connection (what the adapter uses) cannot write
    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO market_bars VALUES ('X','5Min','t',1,1,1,1,1)")
    finally:
        conn.close()


def test_adapter_empty_db_raises(tmp_path):
    db = tmp_path / "empty.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(_GELD_SCHEMA)  # schema but no rows (like Geld's real DB today)
    conn.close()
    with pytest.raises(ValueError):
        load_geld_bars(db, timeframe="5Min")
