# Changelog

All notable changes to Project Emberforge are documented here. This project
adheres to [Semantic Versioning](https://semver.org/) and the format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Five new causal time-series operators** (`dsl/operators.py`): `ts_sum`,
  `ts_skew` (rolling skewness), `ts_zscore` (trailing-window z-score), and
  `ts_argmax`/`ts_argmin` (bars since the window high/low, 0 = now). All use
  trailing windows only and pass the perturbation leakage detector.
- **Three new factor families** (`generate/templates.py`): `skewness` (lottery /
  skew premium), `mean_reversion` (price z-score reversion), and `high_proximity`
  (proximity to the recent high). The semantic classifier gains a `skewness`
  economic family and rules so the new signals dedup correctly.

### Fixed
- **Dynamic leakage detection is now actually enforced.** `assert_no_lookahead`
  (future-perturbation) existed but was only exercised in unit tests — the
  research pipeline ran static causality alone. `run_family_study` now runs the
  perturbation check on every candidate (toggle: `dynamic_leakage_check`, default
  on), so a look-ahead baked into an operator's *implementation* — invisible to
  the static tree check because there's no window literal to inspect — is caught,
  recorded as invalid, and never evaluated or promoted. New
  `tests/test_leakage_pipeline.py` registers exactly such a leaky operator and
  proves the pipeline rejects it (and that disabling the check lets it through).
- **Trial-count penalty is verified end to end** (`tests/test_trial_penalty_pipeline.py`):
  the same factor on the same data scores a strictly lower Deflated Sharpe when the
  family already logged 1,500 trials than when it logged none — proving
  `registry.family_trial_count` really flows into the significance bar in the live
  pipeline, not just in the DSR unit test. Fails if the wiring is ever bypassed.
- **BH/Holm cross-checked against statsmodels** (`tests/test_multiple_testing_reference.py`):
  the hand-rolled Benjamini-Hochberg and Holm corrections match statsmodels'
  `multipletests` to floating-point tolerance — adjusted p-values and reject
  decisions alike — across 120 random p-value vectors (including ties and exact
  0/1 endpoints), so a subtle off-by-one in a rank multiplier can't silently lower
  the significance bar.
- **Geld bundle lost the dataset fingerprint.** `export.from_native_bundle` read
  the v1 `data_fingerprint` from `manifest.expression_hash` (the *factor* hash),
  never opening `data_provenance.json` — so the field duplicated `code_hash` and
  the real dataset fingerprint was dropped. It now reads `data_provenance.json`,
  so `data_fingerprint` (which data) and `code_hash` (which factor) are distinct
  and a Geld paper run traces back to the exact Emberforge dataset.
- **Non-deterministic v1 export.** `to_geld_bundle_v1` stamped `created_at` with
  the wall clock, so converting the same native bundle twice produced different
  bytes. `created_at` is now injectable and `from_native_bundle` carries the
  native bundle's own timestamp through — the conversion is a pure function of the
  bundle on disk, so its checksum is reproducible.
- **Cross-platform bundle reproducibility.** All text file I/O now pins
  `encoding="utf-8"` explicitly. Reports, the demo/pipeline outputs, and — most
  importantly — the candidate-bundle *readers* (`export.validate_bundle`,
  `export.from_native_bundle`, `export.verify_bundle`) previously relied on the
  platform default encoding, so a bundle whose `hypothesis.md`/`report.md`
  contained non-ASCII (`→`, `×`, `—`) hashed differently — or failed to
  read/write — on a Windows (cp1252) machine than on a UTF-8 Linux one. This
  threatened the SHA-256 checksum contract that the offline Geld hand-off relies
  on. Fixes six tests that failed under a non-UTF-8 default locale.

### Added
- **Encoding regression guard** (`tests/test_encoding.py`): a non-ASCII bundle
  round-trips byte-for-byte and still validates, plus a subprocess check that runs
  the whole pipeline under `-X warn_default_encoding` and fails if *any*
  `emberforge.*` text I/O omits an explicit encoding — caught on every platform,
  including UTF-8-default CI.
- **`candidate_bundle_v1` contract tests** (`tests/test_geld_contract.py`): the
  conversion is deterministic (byte-identical output for the same native bundle),
  the v1 field surface is frozen (any add/remove/rename fails loudly, forcing an
  explicit Geld-side sync), and the dataset fingerprint / code hash / trial count
  provably carry through.

### Changed
- **CI now runs on Windows too** (`ci.github-workflow.yml`): the test matrix adds
  `windows-latest` alongside `ubuntu-latest`, so the cross-platform encoding
  guarantee is exercised on the platform where it originally broke.

## [0.1.0] — 2026-08-02

First tagged release. An AI-assisted factor-research platform with
false-discovery control — a research system, not a trading bot. Runs offline with
no credentials, no paid data, and no LLM API key.

### Core (MVP)
- Declarative, typed factor **DSL** (parse → validate → canonicalize → hash), with
  a closed operator set and no arbitrary-code execution path.
- **Causal computation engine** with an explicit preprocessing pipeline; static
  and perturbation-based **look-ahead detection**.
- Cross-sectional **analytics**: IC (+ decay), quantiles, diagnostic long/short
  portfolios, turnover, coverage.
- **Experiment registry** (SQLite) recording every attempt — including failures —
  with lineage, git provenance, and family trial counts.
- **Holdout governance**: development / validation / locked-test partitions,
  research budgets, and gated, logged locked-test access.
- **Multiple testing**: Benjamini–Hochberg, Holm, Deflated Sharpe, PBO (CSCV),
  circular block bootstrap.
- Three-layer **deduplication** (syntactic hash, empirical correlation, semantic
  family) and a novelty report.
- Standardized **reports** (Markdown + JSON) separating raw from adjusted evidence.
- Offline, checksummed, **human-approval-gated candidate bundles** — the only,
  one-way channel to Project Geld.
- Deterministic template + mutation generators, and an optional mock-AI generator.
- End-to-end demo and a CLI.

### Phase B
- First-class **point-in-time universe** support (static / PIT / survivorship /
  research-only), applied PIT-safely.
- **Robustness & regime analysis** (sub-period stability, volatility regimes,
  parameter sensitivity).
- **Purged/embargoed cross-validation**.
- Constrained autonomous **research agent** (least-explored-family selection,
  development-window-only screening, never touches the locked test, promotes only
  via the multi-gate decision function).

### Phase C
- **White's Reality Check** and **Hansen's SPA** (family-level data-snooping
  tests).
- Optional real **Anthropic LLM provider** (`claude-opus-5`) behind the same
  protocol as the offline mock; opt-in via the `[llm]` extra — the core stays
  offline.

### Phase C+
- **Combinatorial Purged CV** (a second PBO estimate) and per-path OOS
  distributions.
- Transaction-cost & **capacity model** (commission + half-spread +
  √-participation market impact + short borrow) with per-name/volatility-aware
  capacity and a cost-sensitivity curve.
- AI generation wired into the research agent.

### Hardening
- **Walk-forward** (sequential out-of-sample) evaluation.
- Standalone **bundle validator** that independently re-parses, re-checks
  causality, and recomputes the hash of an exported candidate.
- **Vectorized analytics** (~14× faster quantiles, identical output).
- **Property-based DSL fuzzing** (Hypothesis).
- Read-only **Geld adapter** integration test against Geld's exact schema.

### Tooling
- Ruff lint config, MIT `LICENSE`, `py.typed` marker, CSV/Parquet loader
  fixtures, and a GitHub Actions CI workflow (prepared; needs a token with the
  `workflow` scope to push).

[0.1.0]: https://github.com/Jiang6082/project-emberforge/releases/tag/v0.1.0
