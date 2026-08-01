# Implementation Report — Project Emberforge (Phase A MVP + Phase B)

## 1. Architecture summary

Emberforge is a typed, modular `src/` package implementing an AI-assisted
factor-research workflow with false-discovery control. Data flows:
`hypothesis → DSL (FactorSpec) → causal compute → analytics → {dedup, stats,
registry} → decision → report → human-approved offline bundle`. Full detail in
[ARCHITECTURE.md](ARCHITECTURE.md). ~3,000 lines of library code across 12
sub-packages.

## 2. File tree (source & tests)

```
src/emberforge/
  dsl/        nodes, parser, operators, canonical, causality, spec
  data/       schema (+fingerprint), synthetic, loaders (csv/parquet/geld-ro)
  compute/    engine (causal eval + preprocessing + look-ahead detector)
  analytics/  ic, portfolio, evaluate_factor
  stats/      multiple_testing, deflated_sharpe, pbo, bootstrap
  dedup/      syntactic, empirical, semantic, novelty
  registry/   db, gitinfo, holdout governance
  generate/   templates, mutate, ai (mock provider)
  research/   decision, pipeline
  report/     candidate, family
  export/     bundle (+verify)
  cli.py, demo.py
tests/        11 test modules (dsl, compute, analytics, stats, dedup,
              registry, generate, export, geld_boundary, demo, conftest)
docs/         10 documents
```

## 3. Setup & demo commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                       # 65 tests
python -m emberforge.demo    # end-to-end; writes runtime/demo/
```

## 4. Test results

**83 passed** (no network, no credentials, no Geld access) — 65 Phase A + 18
Phase B. Coverage spans:
expression parsing, canonicalization/hashing, causal lagging, invalid
future-looking expressions, rolling windows, missing data, IC calculations,
quantile construction, costs, deduplication, FDR adjustments, Deflated Sharpe,
PBO, experiment persistence, lineage, holdout-access tracking, deterministic
generation, AI schema validation, malformed AI output, candidate export, bundle
checksums, and the Project Geld read-only boundary.

## 5. Example generated report

The demo's survivor `momentum_20` (the factor matching the data's embedded
signal):

| metric | value |
|---|---|
| periods | 379 |
| mean IC | 0.073 |
| IC t-stat | 4.68 |
| LS Sharpe | 2.53 |
| turnover | 0.17 |
| BH-adjusted p | 0.0001 → survives FDR |
| decision | `research_survivor` (explicitly **not** "proven alpha") |

Full Markdown at `runtime/demo/reports/momentum_20.md`; aggregate dashboard at
`runtime/demo/family_report.md`.

## 6. Example candidate bundle

`runtime/demo/candidate_bundle/` contains `manifest.json, factor.json,
hypothesis.md, evaluation.json, lineage.json, data_provenance.json, report.md,
checksums.txt`. `verify_bundle` returns `checksums_ok = True`; the manifest's
`approval_state` is `human_approved`. `factor.json` carries only the declarative
expression + hash (no executable code).

The constrained agent produces its own report, e.g.
`{family: momentum, n_candidates_evaluated: 4, survivors: [momentum_60],
n_duplicates: 2, holdout_accesses: 0, stopped_reason: search space exhausted}`.

## 7. How trial counts & holdout access are enforced

* Every experiment — including failures and duplicates — is written to the SQLite
  registry **before** statistics run. `family_trial_count()` is the number of
  hypotheses fed to Benjamini–Hochberg/Holm and the `N` in the Deflated Sharpe
  expected-maximum penalty. In the demo, `N = 24`.
* The locked test is gated by `HoldoutGovernor`: each access is recorded in a
  `holdout_access` table, flips the experiment's `holdout_viewed` flag, warns on
  repeat access, and raises `BudgetExceeded` past the cap. `ResearchBudget` also
  caps candidates per family and mutations per lineage.

## 8. How duplicate factors are detected

Three layers: **syntactic** (canonical-expression SHA-256 — `add(a,b)` ≡
`add(b,a)`); **empirical** (aligned factor-score correlation above a threshold
with a minimum overlap); **semantic** (deterministic rule-based family
classification). The pipeline uses keep-first semantics: a candidate is a
duplicate only if it matches an *earlier* candidate, so the first occurrence
survives and later copies are flagged. In the demo, `momentum_20_dup`
(`ts_delta(close,20)`) is flagged as a duplicate of `momentum_20`.

## 9. Boundary with Project Geld

Emberforge is fully independent. Enforced by `tests/test_geld_boundary.py`:
(a) no `import geld` / `from geld` anywhere in the package; (b) the only
Geld-touching code (`load_geld_bars`) opens SQLite read-only (`mode=ro`);
(c) the pipeline writes only under its own output directory. Communication is a
one-way, offline, human-approved, checksummed bundle. Geld is never modified,
never queried live, and cannot be traded by Emberforge. See
[PROJECT_GELD_INTERFACE_NOTES.md](PROJECT_GELD_INTERFACE_NOTES.md).

## 10. Phase B additions (implemented)

* **Point-in-time universe** (`emberforge.universe`) — static / point-in-time /
  survivorship-stressed / research-only variants. Membership is lagged one bar so
  a change observed at `t` can only affect `t+1`; each universe is fingerprinted
  and recorded per experiment. Wired through `compute_factor`, `evaluate_factor`,
  and `run_family_study`.
* **Robustness & regime analysis** (`emberforge.robustness`) — sub-period
  stability, causal volatility-regime IC, and parameter-sensitivity surfaces in a
  `RobustnessReport`. CLI: `emberforge factor robustness`.
* **Constrained research agent** (`emberforge.agent.ResearchAgent`) — picks the
  least-explored family, screens on the development window only, mutates
  near-misses under budget, records everything, and promotes only via the
  multi-gate decision function. Asserts `holdout_accesses == 0`. CLI:
  `emberforge research-agent run`.
* **Purged & embargoed cross-validation** (`emberforge.stats.cv`).

All guardrails are enforced in code and covered by `tests/test_agent.py`,
`tests/test_universe.py`, `tests/test_robustness.py` (18 new tests, **83 total**).

## 11. Known limitations & next steps

* Synthetic/small data; the IC t-statistic assumes iid periods (stated in
  reports). Diagnostic portfolios ignore real fills, borrow, and capacity.
* PBO/DSR are documented approximations; White's Reality Check and Hansen's SPA
  remain design-only extension points (Phase C).
* A networked LLM provider is intentionally omitted from the offline core; the
  `LLMProvider` protocol and a deterministic mock are in place. See
  [ROADMAP.md](ROADMAP.md).

## Acceptance criteria — status

| Criterion | Status |
|---|---|
| Runs independently of Geld | ✅ |
| Cannot submit trades | ✅ (no broker code exists) |
| No real credentials required | ✅ |
| Factor expressions declarative & validated | ✅ |
| Causality tested | ✅ (static + perturbation) |
| Every experiment recorded | ✅ |
| Failed candidates stay visible | ✅ |
| Duplicates identified | ✅ (3 layers) |
| Trial counts influence statistics | ✅ (DSR/FDR use registry count) |
| Locked holdout governed & tracked | ✅ |
| Multiple-testing implemented & documented | ✅ (BH, Holm, DSR, PBO, bootstrap) |
| Reports reproducible | ✅ (reproduction command in each report) |
| Exports immutable & checksummed | ✅ |
| Exports require human approval | ✅ (`ApprovalError` otherwise) |
| Geld communication offline & one-way | ✅ |
| Geld unmodified | ✅ |
