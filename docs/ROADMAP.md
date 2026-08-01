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

Still open:

* Combinatorial purged cross-validation (CPCV) as an alternative to CSCV PBO.
* Transaction-cost and capacity modelling beyond the current bps proxy.

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
