# AI-Assisted Generation & the Constrained Research Agent

## AI generation (implemented, mock by default)

`emberforge.generate.ai` defines a provider abstraction so an LLM is **optional**.
The default `MockProvider` is deterministic and offline, so the whole system —
including the test suite and demo — runs with no API key and no network.

### The AI emits structured JSON, never code

A proposal is a JSON object validated against the factor schema before it can
become a `FactorSpec`. Required keys: `factor_id, expression,
economic_hypothesis, expected_sign, required_fields`. The prompt template also
asks for `causal_explanation, failure_modes, likely_correlation,
why_survives_costs, falsification_tests`.

```python
from emberforge.generate import generate_ai, MockProvider
spec = generate_ai("underexplored family: volatility", provider=MockProvider())
```

`parse_ai_factor` rejects malformed JSON, missing keys, and any expression that
fails DSL validation (e.g. a negative lag). The `expression` is run through the
same parse → validate → causality pipeline as any other factor — an AI cannot
smuggle in a look-ahead or arbitrary Python.

### Plugging in a real LLM

Implement the `LLMProvider` protocol (`model: str`, `complete(prompt) -> str`)
and pass it to `generate_ai`. The model id and a prompt hash are recorded on the
experiment for reproducibility.

## Deterministic generators (implemented)

* **Templates** (`generate.generate_templates`) — parametrized grammars
  (momentum, reversal, volatility, volume, trend) over a set of horizons. Fully
  deterministic and reproducible.
* **Mutation** (`generate.mutate_family`) — change exactly one window literal,
  recording the parent so lineage reads as an edit history.

## Constrained research agent (Phase B — implemented)

`emberforge.agent.ResearchAgent` composes the generators, the family pipeline,
the registry, budgets, and the decision function into a bounded loop. The
guardrails are enforced in code and covered by `tests/test_agent.py`.

```python
from emberforge.agent import ResearchAgent
from emberforge.data import make_synthetic
from emberforge.registry import ExperimentRegistry
from emberforge.registry.holdout import ResearchBudget

agent = ResearchAgent(make_synthetic(seed=7), ExperimentRegistry("runtime/agent.sqlite3"),
                      budget=ResearchBudget(max_candidates=40))
report = agent.run(families=["momentum", "volatility"])
print(report.summary())
```

```bash
emberforge research-agent run --families momentum,volatility --budget 40
```

**What it does:** picks the *least-explored* family (from registry trial counts),
seeds candidates from templates, screens them on the **development window only**,
mutates the most promising near-misses (bounded per lineage), runs one family
study (which records every experiment and applies the full statistical gauntlet),
and returns a report.

**May:** inspect prior experiments, identify underexplored families, propose
candidates, run development-period tests, review failures, propose limited
mutations, stop when its budget is exhausted, prepare a report.

**May not — enforced in code:**

| Prohibition | Enforcement |
|---|---|
| Run indefinitely | `ResearchBudget.max_candidates` caps the run; `room = budget − prior trials` |
| Hide failed attempts | every candidate goes through `run_family_study`, which records all |
| Inspect the locked test | the agent only ever sees `data.subset(dev_window)`; it asserts `holdout_accesses == 0` |
| Inflate trial counts | trial count comes from the registry, which the agent only appends to |
| Promote on Sharpe alone | promotion is the multi-gate `decide()` (FDR + Deflated Sharpe + novelty) |
| Touch Project Geld | imports nothing from `geld.*`; contains no brokerage code |

**Budgets** (`registry.holdout.ResearchBudget` / `HoldoutGovernor`): max
candidates per family, max holdout accesses, max mutations per lineage.
