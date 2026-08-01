# Architecture

Emberforge is a typed, modular `src/` package. Each stage of the research
workflow is an independent module with a narrow contract, so stages can be
tested and replaced in isolation.

## Data flow

```
                 ┌────────────┐
 hypothesis ───► │  dsl       │  parse → validate → canonicalize → hash → FactorSpec
                 └─────┬──────┘
                       │ FactorSpec (declarative, immutable)
                 ┌─────▼──────┐
 MarketData ───► │  compute   │  causal evaluation + preprocessing → score matrix
                 └─────┬──────┘
                       │ scores (time × symbol)
                 ┌─────▼──────┐
                 │ analytics  │  IC, decay, quantiles, diagnostic LS returns
                 └─────┬──────┘
          ┌────────────┼─────────────┬───────────────┐
    ┌─────▼─────┐ ┌────▼─────┐ ┌─────▼──────┐ ┌───────▼───────┐
    │  dedup    │ │  stats   │ │  registry  │ │  research     │
    │ 3 layers  │ │ BH/Holm/ │ │ SQLite,    │ │ decision +    │
    │           │ │ DSR/PBO/ │ │ lineage,   │ │ pipeline      │
    │           │ │ bootstrap│ │ holdout    │ │ orchestration │
    └───────────┘ └──────────┘ └────────────┘ └───────┬───────┘
                                                       │
                              ┌────────────┐    ┌──────▼──────┐
                              │  report    │◄───┤  generate   │ templates/mutate/AI
                              └─────┬──────┘    └─────────────┘
                                    │ human approval
                              ┌─────▼──────┐
                              │  export    │  offline, checksummed bundle → (manual) Geld
                              └────────────┘
```

## Module map (`src/emberforge/`)

| Module | Responsibility |
|---|---|
| `dsl/` | Expression nodes, parser, operator registry, canonicalization/hashing, causality validation, `FactorSpec` |
| `data/` | `MarketData` panel + provenance/fingerprint, synthetic generator, CSV/Parquet + read-only Geld loaders |
| `compute/` | Causal evaluation engine, preprocessing pipeline, data-driven look-ahead detector |
| `analytics/` | IC statistics + decay, quantile analytics, diagnostic long-short portfolios, cost & capacity model, `evaluate_factor` |
| `stats/` | Benjamini–Hochberg, Holm, Deflated Sharpe, PBO (CSCV **and** CPCV), White's Reality Check, Hansen's SPA, purged/embargoed CV, circular block bootstrap |
| `dedup/` | Syntactic (hash), empirical (correlation), semantic (family) dedup + novelty report |
| `registry/` | SQLite experiment registry, lineage, git provenance, holdout governance & budgets |
| `universe/` | Point-in-time universe membership (static/PIT/survivorship/research-only), PIT-safe eligibility |
| `robustness/` | Sub-period stability, volatility-regime IC, parameter sensitivity |
| `generate/` | Template, mutation, and AI (mock-by-default) generators |
| `agent/` | Constrained autonomous research agent (Phase B) |
| `research/` | Decision framework + end-to-end family pipeline |
| `report/` | Per-candidate and aggregate family reports (Markdown + JSON) |
| `export/` | Offline candidate-bundle writer + checksum verifier |
| `cli.py`, `demo.py` | CLI entry point and end-to-end demonstration |

## Key design decisions

* **Declarative factors only.** A factor is a small typed tree (`Field`/`Const`/
  `Call`), never arbitrary Python. Parsing, hashing, and safe evaluation all
  operate on this closed representation.
* **Causal by construction.** Time-series operators use trailing windows and
  non-negative shifts; cross-sectional operators act within a single timestamp.
  Negative lags are rejected statically, and a perturbation-based detector
  catches any forward dependence dynamically.
* **Separation of concerns.** Factor computation never constructs portfolios;
  diagnostic portfolios live in `analytics` and are explicitly non-executable.
* **The registry is the source of truth for trial counts**, which feed the
  Deflated Sharpe penalty and FDR adjustments.

## Dependencies (justified)

pandas + NumPy (panel math), SciPy/statsmodels (distributions, stats),
scikit-learn (reserved for Phase-B neutralization/CV), Pydantic (schema
validation of `FactorSpec` and metadata), PyArrow (Parquet I/O), SQLite (stdlib;
zero-ops persistence), PyYAML (config). Polars is intentionally **not** a
dependency in v1.
