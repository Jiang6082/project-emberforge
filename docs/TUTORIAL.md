# Using Emberforge — a practical guide

**First, set expectations.** Emberforge is **not a server or a bot you leave
running.** It is a **command-line tool + Python library** you invoke to do factor
research. "Up and running" means: installed, pointed at some data, and producing
reports and export bundles on demand. Nothing runs in the background; nothing
places trades; nothing needs credentials.

You interact with it three ways: the **CLI** (`emberforge …`), the **Python
library** (`import emberforge`), and the **end-to-end demo**.

---

## 1. Install (once)

```bash
cd project-emberforge
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # add ,llm for the real Anthropic provider: ".[dev,llm]"
```

Verify:

```bash
emberforge --version
pytest -m "not slow"               # fast sanity check (~30s)
```

## 2. See the whole workflow in one command

```bash
emberforge demo --out runtime/demo
```

This generates a known factor + noise + duplicates, evaluates them, applies the
full statistical gauntlet, rejects the weak/duplicate ones, keeps one survivor,
and exports a checksummed bundle. Look in `runtime/demo/`:

- `reports/<factor>.md` — per-candidate report (raw vs. adjusted evidence),
- `family_report.md` — ranked dashboard of everything tried,
- `candidate_bundle/` — the exported survivor,
- `registry.sqlite3` — every experiment, including the failures.

---

## 3. Point it at *your* data

Emberforge needs a panel of daily bars. Three sources:

**a) Synthetic (default)** — no setup; good for learning and testing:

```bash
emberforge factor evaluate "ts_returns(close, 20)"
```

**b) Your own CSV files** — one file per field, timestamp index + one column per
symbol (`close.csv`, `volume.csv`, …). See `examples/data/csv/` for the exact
shape:

```bash
emberforge data validate  --csv-dir path/to/csv
emberforge factor evaluate "cs_rank(divide(volume, ts_mean(volume,20)))" --csv-dir path/to/csv
```

In Python you can also load long-form Parquet (`[timestamp, symbol, field,
value]`) via `emberforge.data.load_parquet`.

**c) Project Geld's cached bars (read-only)** — if Geld has fetched bars, read
them without ever writing back:

```bash
python examples/geld_adapter_smoke.py ../project-geld/data/geld.sqlite3 5Min
```

(Geld's cache is empty until it runs against Alpaca with credentials, so this
skips cleanly until then.)

---

## 4. Evaluate one factor

Factors are written in a small, safe language (never Python). Examples:

```
ts_returns(close, 20)                          # 20-day momentum
neg(ts_std(ts_returns(close, 1), 25))          # low-volatility premium
cs_rank(divide(volume, ts_mean(volume, 20)))   # relative-volume spike
```

```bash
emberforge factor validate    "ts_returns(close, 20)"      # parse + causality check
emberforge factor evaluate    "ts_returns(close, 20)"      # IC, Sharpe, turnover, capacity…
emberforge factor robustness  "ts_returns(close, 20)" --template "ts_returns(close,{w})" --params 10,20,30,40
emberforge factor walkforward "ts_returns(close, 20)" --windows 5   # sequential out-of-sample
```

A negative/zero look-back is rejected as look-ahead before it can run.

---

## 5. Let the research agent search for you

The constrained agent proposes candidates in the least-explored family, screens
them on the development window only (never the locked test), and promotes only
through the multi-gate decision function:

```bash
emberforge research-agent run --families momentum,volatility --budget 40 \
    --registry runtime/agent/registry.sqlite3
# add --ai mock  (offline)  or  --ai anthropic  (needs the [llm] extra + ANTHROPIC_API_KEY)
```

Then inspect what it tried:

```bash
emberforge experiment list --registry runtime/agent/registry.sqlite3
emberforge experiment show <experiment_id> --registry runtime/agent/registry.sqlite3
```

---

## 5b. Or run the fully automated pipeline (no human gate)

If you want *search → auto-approve → export → report* in one command, with a
human-readable HTML dashboard written every run:

```bash
emberforge pipeline run --families momentum,reversal,volatility --out runtime/pipeline
# --ai mock|anthropic --n-ai 3   to also request LLM candidates
# --csv-dir path/to/csv          to run on your own data
# --no-approve                   to write reports but NOT auto-export
```

It runs **one study per search family** (so momentum is judged against momentum,
not against its own mirror image), keeps the **strongest** of each correlated
cluster, and auto-exports every survivor as a bundle stamped
`approval_state: "auto_approved"` (honest provenance — no fake human sign-off).
Outputs land in `runtime/pipeline/`:

- **`report.html`** — the nice dashboard to open in a browser (raw vs. adjusted
  evidence, survivors highlighted),
- `family_report.md`, `reports/<factor>.md`, `bundles/<factor>/` (validated), and
  `summary.json`.

Every exported bundle passes `emberforge export verify` on its own.

## 6. Export a survivor and verify the bundle

Export requires an explicit human-approved decision (the demo does this for you).
Anyone — including Project Geld — can independently validate a bundle:

```bash
emberforge export verify runtime/demo/candidate_bundle
```

This re-parses the expression, re-runs the causality checks, recomputes the hash,
and confirms schema + approval — not just checksums.

---

## 7. Use it as a library

```python
from emberforge.data import make_synthetic          # or load_csv_dir / load_parquet
from emberforge.dsl import make_factor
from emberforge.analytics import evaluate_factor
from emberforge.registry import ExperimentRegistry
from emberforge.research import run_family_study, walk_forward
from emberforge.generate import generate_templates

data = make_synthetic(seed=7)

# one factor
ev = evaluate_factor(make_factor("mom20", "ts_returns(close, 20)"), data)
print(ev.ic.mean_ic, ev.portfolio.sharpe, ev.capacity_usd)

# a whole family, recorded with full statistics
reg = ExperimentRegistry("runtime/lib/registry.sqlite3")
study = run_family_study("momentum", generate_templates(which=["momentum"]), data, reg)
print("survivors:", study.survivors)

# out-of-sample decay
print(walk_forward(make_factor("mom20", "ts_returns(close, 20)"), data).summary())
```

---

## 8. The end-to-end loop, in one sentence

Write a hypothesis → express it in the DSL → `evaluate` (or let the agent search)
→ read the report (raw **vs.** adjusted evidence) → if it survives every gate,
approve and **export** a bundle → hand that offline bundle to Project Geld for
manual validation. Everything you tried stays in the registry, which is what
makes the one survivor trustworthy.

## What "production" looks like

There is no daemon to deploy. A realistic cadence is: schedule
`emberforge research-agent run` (or a Python driver) on your own data, review the
family report, and export approved candidates. Emberforge stays a research tool;
Project Geld remains the only thing that ever trades, and only from bundles a
human has approved and copied over by hand.
