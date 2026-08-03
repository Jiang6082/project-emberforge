# Roadmap

## Phase A — MVP (done)

Synthetic data · factor DSL · causal computation · analytics · experiment
registry · three-layer deduplication · multiple-testing (BH, Holm, Deflated
Sharpe, PBO, block bootstrap) · reporting · offline checksummed bundle export ·
deterministic + mutation + mock-AI generation · end-to-end demo · full test
suite · docs.

Acceptance criteria are met — see
[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md).

## Phase B — advanced research integrity (implemented)

* ✅ **Point-in-time universe** (`emberforge.universe`) as a first-class input:
  static, point-in-time, survivorship-stressed, and research-only variants;
  membership is lagged one bar so a change at `t` cannot affect `t`; fingerprinted
  and recorded per experiment.
* ✅ **Robustness & regime analysis** (`emberforge.robustness`): sub-period
  stability, causal volatility-regime splits, and parameter-sensitivity surfaces,
  combined in a `RobustnessReport`.
* ✅ **Constrained research agent** (`emberforge.agent`): picks the least-explored
  family, screens on the development window only, mutates near-misses under
  budget, and promotes only through the multi-gate decision function. Hard
  candidate/holdout/mutation budgets; asserts zero locked-test access.
* ✅ **Purged & embargoed cross-validation** (`emberforge.stats.cv`).

Still open in this track:

* **Real LLM provider** behind the existing `LLMProvider` protocol (the interface
  and a mock exist; a networked implementation is intentionally omitted from the
  offline core).
* **Cross-feed stability** (needs a second data feed).

## Phase C — statistical depth & real LLM (implemented)

* ✅ **White's Reality Check** and **Hansen's SPA** (`stats.reality_check`) —
  family-level data-snooping tests over the best-of-N, wired into
  `run_family_study` and shown in every candidate report.
* ✅ **Optional real LLM provider** (`generate.AnthropicProvider`, Anthropic
  `claude-opus-5` by default) behind the existing `LLMProvider` protocol —
  opt-in via `pip install 'emberforge[llm]'`, structured-JSON output, refusal
  handling; the core stays fully offline.

## Phase C+ — completed extras

* ✅ **Combinatorial Purged CV** (`stats.cpcv`) — a second PBO estimate over
  combinatorial backtest paths, reported alongside CSCV PBO.
* ✅ **Cost & capacity model** (`analytics.costs`) — commission + half-spread +
  √-participation market impact + short borrow, with a bisection **capacity**
  estimate and a cost-sensitivity curve, surfaced in every candidate report.
  See [COST_AND_CAPACITY.md](COST_AND_CAPACITY.md).
* ✅ **AI generation wired into the research agent** — the agent optionally asks
  an `LLMProvider` (mock or Anthropic) for candidates, validated like any other.

## Polish (implemented)

* ✅ **Per-name, volatility-calibrated capacity** — `estimate_capacity` accepts
  per-name ADV and daily-vol arrays (Almgren-style √-impact); the least-liquid /
  most-volatile names dominate, and `evaluate_factor` derives both from the
  dataset.
* ✅ **CPCV path distributions** — `cpcv_path_distribution` reports a single
  factor's out-of-sample Sharpe across combinatorial paths (median, 5th pct,
  fraction positive), shown per candidate.
* ✅ **Repo hygiene** — `LICENSE` (MIT) and a `py.typed` marker so the typed
  package ships its types. A GitHub Actions CI workflow (`pytest` on 3.11/3.12 +
  boundary check) is prepared at `.github/workflows/ci.yml`; it needs a token with
  the `workflow` scope to push (`gh auth refresh -s workflow`, then
  `git add -f .github/workflows/ci.yml`).

## Hardening (implemented)

* ✅ **Walk-forward evaluation** (`research.walk_forward`, CLI `factor
  walkforward`) — sequential out-of-sample windows after an in-sample warm-up,
  reporting per-window IC/Sharpe and OOS stability, so factor decay is visible
  instead of hidden behind a single split.
* ✅ **Standalone bundle validator** (`export.validate_bundle`, CLI `export
  verify`) — re-parses the exported expression, re-runs causality, recomputes the
  hash, and checks schema + approval.
* ✅ **Vectorized analytics** — `quantile_buckets`/`turnover`/`score_autocorr`
  rewritten without row-wise apply (~14× faster, identical output).

## Remaining / future

* Per-name ADV as a rolling time series (currently a per-symbol median snapshot)
  and venue-calibrated impact coefficients.
* Walk-forward with per-window parameter *re-selection* (the current version
  evaluates a fixed factor; the window framing is the hook for it).

## Phase D — interoperability

* A richer intraday data path (Emberforge is daily-first today).
* An optional, human-run Geld-side validator that consumes the candidate bundle
  schema (built in Geld, not from here).
* Signed, reviewed factor plugins if a non-declarative execution path is ever
  justified.

## Explicit non-goals

Distributed schedulers, web apps/frontends, live-trading integration, cloud
infrastructure, and anything that would let Emberforge place a trade or modify
Project Geld.
