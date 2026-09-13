# Current Project Geld interface

Verified against Geld `bece5c4` and the paired September 2026 integrity changes.

Emberforge generates/evaluates declarative research factors. Geld is a separate
Python research, backtest and paper-execution engine under `project_geld`, with
its own cache, configuration, candidate evaluator, OOS gates, state machine,
run manifests and paper controls. Older notes claiming these are absent are
obsolete.

There is no automatic live link. Emberforge has no broker client and never
changes Geld's repository, credentials, configuration or accounts. A user
explicitly exports/copies a candidate file and invokes Geld's own commands.

## Read current Geld data

Current Geld historical outputs use long-form CSV/CSV.gz with `timestamp,
symbol, open, high, low, close, volume` and optional `vwap`:

```python
from emberforge.data import load_geld_csv

data = load_geld_csv(
    "/path/to/project-geld/artifacts/research-broad/selected-bars.csv.gz",
    frequency="daily", feed="sip", adjustment="all",
)
```

Supply feed/adjustment only when verified from the source run. The CLI form
below is for daily bars and records both as unknown because a CSV alone does
not prove them. No VWAP is invented, and duplicate timestamp/symbol rows fail.

```text
emberforge data validate --geld-csv /path/to/selected-bars.csv.gz
emberforge pipeline run --geld-csv /path/to/selected-bars.csv.gz --families momentum --no-approve
```

The legacy `load_geld_bars` SQLite adapter remains available in read-only mode
for old `market_bars` databases. That is not the current cache layout. Intraday
analytics need explicit frequency, annualization and execution assumptions.

## Offline handoff

1. Review the native bundle, recorded evidence and approval state.
2. `from_native_bundle` independently verifies it before format conversion.
3. `export_geld_bundle_v1` writes a data-only JSON candidate.
4. Geld validates and imports it into quarantine with paper disabled. Re-import
   cannot erase an existing record's state/history.
5. Geld rechecks schema, approval and expression integrity, then applies its
   independent OOS/cost gates and optional batch FDR to supplied market data.
6. Passing candidates may advance to order-free shadow. Paper promotion remains
   a separate manual step within Geld; Emberforge cannot perform it.

Unsupported frequencies are not silently relabeled. Actual preprocessing is
retained. An Emberforge long/short diagnostic and Geld's default long-only
candidate strategy are different portfolios, so their returns are not
interchangeable. `auto_approved` records programmatic screening, not human
approval or untouched holdout success.

See [the audit](AUDIT_2026-09-13.md) for remaining statistical and data limitations.
