# Project Emberforge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A Python factor-research system with a constrained expression language, an SQLite experiment registry, and checksummed candidate exports.**

[Interactive walkthrough](https://jiang6082.github.io/projects/emberforge/) · [Architecture](docs/ARCHITECTURE.md) · [Portfolio](https://jiang6082.github.io/)

For a code review, start with the [DSL parser](src/emberforge/dsl/parser.py), [property-based DSL tests](tests/test_dsl_properties.py), [holdout governance](src/emberforge/registry/holdout.py), and [independent export validator](src/emberforge/export/validator.py). The core runs offline; an LLM provider is optional. The walkthrough's threshold controls use invented p-values, separately labeled from the recorded synthetic research demo.

Emberforge helps you invent, test, and vet *factors* (systematic signals that try
to predict which stocks will outperform). The hard part of factor research isn't
finding something that looks good on historical data — with enough tries, pure
noise will. The hard part is telling a real edge apart from a lucky fluke.
Emberforge is engineered around that problem: it records **every** attempt,
penalizes results for how many things you tried, hunts for hidden look-ahead
bugs, flags rediscovered duplicates, and refuses to call anything "proven."

> Emberforge is a **research system, not a trading bot.** It has no brokerage
> code, needs no credentials, places no orders, and requires no paid data or LLM
> API key to run. It talks to its companion trading project (Project Geld) only
> through a manual, one-way, offline file — never live.

---

## Why it exists

A quant researcher's workflow is a minefield of ways to accidentally lie to
yourself:

| Trap | What Emberforge does about it |
|---|---|
| A signal secretly peeks at the future | Rejects non-causal expressions statically **and** catches leakage dynamically by perturbing future data |
| You try 1,000 factors and cherry-pick the best | Records every trial and feeds that count into the statistics (Deflated Sharpe, FDR) so the winner's bar rises with the number of attempts |
| You reuse the test set until something passes | Governs and logs every locked-holdout access, warns on reuse, and hard-blocks past a budget |
| You "discover" the same idea five times | Three-layer duplicate detection (formula, correlation, economic family) |
| A high Sharpe ratio dazzles you | Promotion requires statistical *and* stability *and* novelty gates — a high Sharpe alone never promotes |

The strongest label any candidate can earn is **`research_survivor`**, never
"alpha."

---

## What it does, end to end

```
Research hypothesis
   → Declarative factor specification (a safe, typed mini-language — never arbitrary code)
   → Causal factor computation (no future data can leak in)
   → Data-quality & leakage checks
   → Cross-sectional analytics (IC, decay, quantiles, diagnostic long/short)
   → Deduplication & novelty analysis
   → Train / validation evaluation
   → Multiple-testing adjustment (Benjamini–Hochberg, Holm, Deflated Sharpe, PBO, bootstrap)
   → Robustness & regime analysis
   → Candidate decision
   → Human approval
   → Offline, checksummed export bundle
```

Every candidate, failed experiment, and mutation is written to a SQLite
registry. The point of the system is the **record of everything tried** — that's
what lets a reviewer audit how a survivor was selected.

---

## Run the synthetic demo

```bash
git clone https://github.com/Jiang6082/project-emberforge.git
cd project-emberforge
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest                       # full suite, no network / credentials / external data
python -m emberforge.demo    # full research run on deterministic synthetic data
```

**Development.** Run the fast core (skips the end-to-end / bootstrap-heavy tests)
with `pytest -m "not slow"`; lint with `ruff check .`. Installation, tests, and the demo can take several minutes depending on the environment.

The demo plants a known momentum effect in synthetic data, then evaluates the configured candidates, including near-duplicates and other factor families. It records every attempt, labels candidate decisions, and exports a survivor as a checksummed bundle.

The [September 13, 2026 demo snapshot](docs/DEMO_SNAPSHOT.md) recorded **36 candidates: one survivor (`momentum_20`), 24 duplicates, and 11 rejected candidates**, with bundle checksums verified. These are synthetic-demo outcomes, not evidence of market alpha. Approval is preconfigured in the demo code; in a research workflow, a person must review the candidate before approving an export.

Output lands in `runtime/demo/`:

```
registry.sqlite3          every experiment, including the failures
reports/<factor>.md|.json per-candidate reports (raw vs. adjusted evidence)
family_report.md          aggregate dashboard ranking all candidates
candidate_bundle/         the one exported survivor (+ checksums.txt)
summary.json
```

---

## A taste of the factor language

Factors are written in a small, safe expression language — not Python — so they
can be parsed, hashed, deduplicated, and checked for look-ahead:

```
ts_returns(close, 20)                          # 20-day momentum
neg(ts_std(ts_returns(close, 1), 25))          # low-volatility premium
cs_rank(divide(volume, ts_mean(volume, 20)))   # relative volume spike
```

```bash
emberforge factor validate    "ts_returns(close, 20)"
emberforge factor evaluate     "ts_returns(close, 20)" --horizon 1
emberforge factor compare      "ts_returns(close,20)" "ts_delta(close,20)"
emberforge factor robustness   "ts_returns(close,20)" --template "ts_returns(close,{w})" --params 10,20,30,40
emberforge factor walkforward  "ts_returns(close,20)" --windows 5
emberforge generate templates
emberforge experiment list     --registry runtime/demo/registry.sqlite3 --family momentum_family
emberforge research-agent run  --families momentum,volatility --budget 40
emberforge pipeline run        --families momentum,reversal,volatility   # auto: search → export → HTML report
emberforge export verify       runtime/demo/candidate_bundle
emberforge demo
```

A negative or zero look-back is rejected as look-ahead before it can ever run.

---

## Relationship to Project Geld

Emberforge is the **research sibling** of [Project Geld](https://github.com/Jiang6082/project-geld),
a paper-trading bot. The boundary is strict and one-directional:

* Emberforge treats Geld as **read-only** — it never modifies Geld, its config,
  its accounts, or its data.
* The only thing that ever crosses over is a **manual, offline, checksummed
  candidate bundle** that a human reviews and copies. No APIs, no shared
  databases, no hooks, no live link.
* Emberforge cannot place a trade; it contains no brokerage code at all.

This is enforced by tests, not just convention. See
[`docs/PROJECT_GELD_INTERFACE_NOTES.md`](docs/PROJECT_GELD_INTERFACE_NOTES.md).

---

## Documentation

| Doc | Contents |
|---|---|
| [TUTORIAL.md](docs/TUTORIAL.md) | **How to run and actually use it** |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module map and data flow |
| [SCIENTIFIC_METHOD.md](docs/SCIENTIFIC_METHOD.md) | The anti-self-deception design |
| [FACTOR_DSL.md](docs/FACTOR_DSL.md) | The declarative factor language |
| [EXPERIMENT_REGISTRY.md](docs/EXPERIMENT_REGISTRY.md) | Lineage, trial counts, holdout governance |
| [MULTIPLE_TESTING.md](docs/MULTIPLE_TESTING.md) | BH, Holm, Deflated Sharpe, PBO (CSCV/CPCV), White RC, Hansen SPA, bootstrap |
| [COST_AND_CAPACITY.md](docs/COST_AND_CAPACITY.md) | Transaction-cost decomposition & capacity estimate |
| [AI_RESEARCH_AGENT.md](docs/AI_RESEARCH_AGENT.md) | AI generation & the constrained agent |
| [PROJECT_GELD_INTERFACE_NOTES.md](docs/PROJECT_GELD_INTERFACE_NOTES.md) | What Geld is; the boundary |
| [DIVISION_OF_LABOR.md](docs/DIVISION_OF_LABOR.md) | Emberforge vs. Geld — who does what, and why |
| [CANDIDATE_BUNDLE.md](docs/CANDIDATE_BUNDLE.md) | The offline export format |
| [ROADMAP.md](docs/ROADMAP.md) | What's next |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) | Build summary & acceptance evidence |

---

## Status

**Phase A (MVP) complete** — declarative DSL, causal compute, analytics, registry
with lineage and holdout governance, three-layer dedup, the full multiple-testing
suite, reporting, offline bundle export, and deterministic + mock-AI generation.

**Phase B complete** — point-in-time universe support, robustness/regime analysis,
purged/embargoed cross-validation, and the constrained autonomous research agent
(picks the least-explored family, screens on the development window only, never
touches the locked test, and promotes only through the multi-gate decision
function).

**Phase C complete** — White's Reality Check and Hansen's SPA (family-level
data-snooping tests), plus an optional real LLM provider
(`AnthropicProvider`, `claude-opus-5`) behind the same protocol as the offline
mock — install with `pip install 'emberforge[llm]'`; the core stays offline.

**Phase C+ complete** — combinatorial purged cross-validation (a second PBO
estimate), a transaction-cost & capacity model (spread + √-participation market
impact + borrow, with a capacity estimate and cost-sensitivity curve), and
AI-assisted generation wired into the research agent (mock offline, or Anthropic).

**Hardening complete** — walk-forward (sequential out-of-sample) evaluation, a
standalone bundle validator that independently re-parses/re-checks an exported
candidate, vectorized analytics (~14× faster quantiles), and property-based DSL
fuzzing (Hypothesis).

Run `pytest` for the current suite, or `pytest -m "not slow"` for the core checks. Counts and timings depend on the checkout and environment.

**CI status:** the repository currently contains a workflow template at `ci.github-workflow.yml`, outside `.github/workflows/`. It is not an active GitHub Actions workflow. The local test commands above remain the verification entry point. See [ROADMAP.md](docs/ROADMAP.md).

## Disclaimer

Research tooling for studying factor-discovery methodology. Nothing here is
investment advice, and no output is a validated trading strategy.

## License

MIT.
