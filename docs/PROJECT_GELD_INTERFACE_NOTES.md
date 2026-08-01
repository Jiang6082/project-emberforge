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
