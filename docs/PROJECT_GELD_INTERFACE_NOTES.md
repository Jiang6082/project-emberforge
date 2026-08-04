# Project Geld — Interface Notes (read-only inspection)

These notes document what Project Geld **actually is**, based on a read-only
inspection of the local repository. Emberforge never modifies Geld, never touches
its accounts, and never writes into its tree.

## What Geld is

Geld is a small, beginner-readable **5-minute intraday Alpaca paper-trading bot**.
It is *not* a mature quant-data platform. Assuming it has rich data infrastructure
would lead to fabricated conventions, so this document is deliberately explicit
about what exists and what does not.

## What actually exists

### Market data
A single dataclass `Bar` (`geld/storage/models.py`):

| field | type |
|---|---|
| symbol | str |
| timestamp | tz-aware UTC datetime |
| open, high, low, close | float |
| volume | float |
| timeframe | str (default `"5Min"`) |

Bars are fetched live from Alpaca and cached in a SQLite table `market_bars`
(`geld/storage/database.py`) keyed by `(symbol, timeframe, timestamp)`.
Timestamps are stored as ISO-8601 strings.

### Strategy output ("target format")
A `Signal` dataclass: `strategy_name, symbol, direction ∈ {BUY, SELL, HOLD, EXIT},
confidence ∈ [0, 1], reason, timestamp`. That is the entirety of a strategy's
output. There is nothing resembling a cross-sectional factor score.

### Universe
A **static hardcoded list** in `config.yaml`: `SPY, QQQ, NVDA, AAPL, TSLA`.

### Persistence
SQLite tables: `market_bars, strategy_signals, orders, fills, positions,
equity_curve, events`.

### Timestamp / timezone conventions
UTC throughout; tz-aware datetimes in code, ISO strings in SQLite.

## What does NOT exist in Geld (Emberforge introduces these)

Marked absent so nothing is invented:

| Concept | Status in Geld | Emberforge approach |
|---|---|---|
| Feed / adjustment metadata | **absent** | `DatasetMetadata.feed`, `.adjustment` |
| Dataset version / source | **absent** | `DatasetMetadata.version`, `.source` |
| Data fingerprint | **absent** | SHA-256 panel fingerprint |
| Point-in-time universe | **absent** (static list) | first-class PIT universe (Phase B) |
| Survivorship handling | **absent** | universe variants (Phase B) |
| Artifact / manifest system | **absent** | candidate bundle + manifest |
| Candidate validator | **absent** | bundle schema is *designed* to be validated later |

Directories the original brief warned against writing to — of `state/`,
`artifact/`, `universe/`, `paper/` — only `data/` exists. Emberforge writes to
none of them regardless.

## Frequency note

Geld is **5-minute intraday**. Emberforge is **daily-first for research**, with a
read-only adapter (`emberforge.data.loaders.load_geld_bars`) that maps Geld's
5Min `Bar` rows into Emberforge panels (VWAP approximated as `(H+L+C)/3`, since
Geld stores none). The adapter opens Geld's SQLite in read-only mode
(`file:...?mode=ro`) and imports nothing from `geld.*`.

## Verifying the read-only adapter

`emberforge.data.load_geld_bars` is exercised end-to-end against a database built
with Geld's **exact** `market_bars` schema in `tests/test_geld_adapter.py`
(self-contained, no external data), which also proves the connection is
genuinely read-only (a `mode=ro` write raises, and the file is byte-identical
before/after). `examples/geld_adapter_smoke.py` runs the same check against a
*real* Geld database:

```bash
python examples/geld_adapter_smoke.py [path/to/geld.sqlite3] [TIMEFRAME]
```

Note: Geld's real `market_bars` table is **empty today** — Geld only caches bars
after a successful Alpaca fetch, which needs credentials and a live run. Until
then the smoke script skips cleanly. The adapter is verified against the schema
regardless.

## Bundle schema bridge (the two projects diverged)

Geld independently built its own bundle contract, **`candidate_bundle_v1`**
(`geld/candidates/validator.py`): a single JSON with `signal_spec`,
`required_inputs`, `frequency ∈ {1Min,5Min,15Min,1Day}`, `lookback`, and
`approval_status ∈ {draft,approved,rejected}`. Emberforge's *native* bundle is a
folder with different field names, so it does **not** satisfy Geld's validator
as-is.

`emberforge.export.geld_bundle` bridges them — it maps an Emberforge candidate onto
`candidate_bundle_v1` (daily → `1Day`, the synthesized `returns` field → `close`,
`auto_approved` → `approved`, plus a portfolio-construction hint and an evaluation
summary). Emberforge still **never imports Geld** — the contract is mirrored, kept
in sync by hand. The pipeline emits `geld_bundles/<id>.candidate.json` per
survivor, and `examples/verify_against_geld.py` cross-checks them against Geld's
*real* validator (they pass).

Note: even after Geld imports a bundle, its importer only **quarantines** it
(research-only) — nothing is auto-enabled, and Geld's live loop still trades only
the strategies in `config.yaml`. Turning an imported factor into live signals
would need a factor executor on the Geld side, which does not exist yet.

## The boundary — what may cross it

**One way, offline, manual only.** Emberforge → Geld communication is a
versioned, checksummed candidate bundle
([`CANDIDATE_BUNDLE.md`](CANDIDATE_BUNDLE.md)) that a human copies over and Geld
may later validate by hand. There are **no** API calls, shared databases, git
hooks, or brokerage integrations. Nothing about Emberforge changes what Geld
trades. Enforced by `tests/test_geld_boundary.py`:

* Emberforge imports nothing from `geld.*`.
* The Geld adapter opens SQLite read-only (`mode=ro`).
* The pipeline writes only under its own output directory.
