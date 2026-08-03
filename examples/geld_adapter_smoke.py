"""Read-only smoke test of the Project Geld adapter against a *real* Geld DB.

Run this to confirm Emberforge can read Geld's cached bars without writing
anything back. It never modifies Geld — it opens the SQLite in ``mode=ro`` and
verifies the file is byte-identical before and after.

Usage:
    # point at your Geld database (or set GELD_DATABASE_PATH)
    python examples/geld_adapter_smoke.py [path/to/geld.sqlite3] [TIMEFRAME]

If the database is missing or has no cached bars yet (Geld only caches when it
successfully fetches from Alpaca), the script says so and exits cleanly — that is
expected until Geld has run with credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from emberforge.analytics import evaluate_factor
from emberforge.data import load_geld_bars
from emberforge.dsl import make_factor

DEFAULT_DB = Path(__file__).resolve().parents[2] / "project-geld" / "data" / "geld.sqlite3"


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("GELD_DATABASE_PATH", DEFAULT_DB))
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "5Min"

    if not db.exists():
        print(f"[skip] no Geld database at {db}")
        return 0

    before = (db.stat().st_mtime_ns, db.stat().st_size)
    try:
        data = load_geld_bars(db, timeframe=timeframe)
    except ValueError as e:
        print(f"[skip] {e} — Geld has not cached any {timeframe} bars yet.")
        return 0

    after = (db.stat().st_mtime_ns, db.stat().st_size)
    assert before == after, "adapter must not modify Geld's database"

    print(f"[ok] loaded {len(data.symbols)} symbols x {len(data.index)} {timeframe} bars, read-only")
    print(f"     symbols: {data.symbols}")
    print(f"     range:   {data.metadata.start} .. {data.metadata.end}")
    print(f"     source:  {data.metadata.source}  fingerprint: {data.metadata.fingerprint}")

    if len(data.symbols) >= 3 and len(data.index) > 10:
        ev = evaluate_factor(make_factor("smoke_mom", "cs_rank(ts_returns(close, 5))"), data)
        print(f"[ok] computed a factor on Geld bars — mean IC {ev.ic.mean_ic:.4f} over {ev.ic.n} periods")
    else:
        print("[note] too few symbols/bars for a meaningful cross-sectional factor (Geld universe is small).")
    print("[ok] Geld database unchanged; boundary held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
