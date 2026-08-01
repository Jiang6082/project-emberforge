# Roadmap

## Phase A — MVP (done)

Synthetic data · factor DSL · causal computation · analytics · experiment
registry · three-layer deduplication · multiple-testing (BH, Holm, Deflated
Sharpe, PBO, block bootstrap) · reporting · offline checksummed bundle export ·
deterministic + mutation + mock-AI generation · end-to-end demo · full test
suite · docs.

Acceptance criteria are met — see
[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md).

## Phase B — advanced research integrity (next)

* **Point-in-time universe** as a first-class input: historical membership,
  survivorship-stressed and research-only variants, fingerprinted per experiment.
* **Robustness & regime analysis**: sub-period stability, volatility-regime
  splits, parameter-sensitivity surfaces, cross-universe and cross-feed stability.
* **Constrained research agent**: compose the existing generators, registry,
  budgets, decision function, and reporting into an autonomous loop with hard
  compute/candidate/holdout budgets and the prohibitions in
  [AI_RESEARCH_AGENT.md](AI_RESEARCH_AGENT.md).
* **Real LLM provider** behind the existing `LLMProvider` protocol.
* **Purged & embargoed cross-validation** for the evaluation split.

## Phase C — statistical depth

* White's Reality Check and Hansen's SPA (extension points already reserved).
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
