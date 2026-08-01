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

## Constrained research agent (Phase B — designed, not yet wired)

The agent will operate under hard budgets and explicit prohibitions.

**May:** inspect prior experiments, identify underexplored families, propose
candidates, run development-period tests, review failures, propose limited
mutations, stop when its budget is exhausted, prepare a report.

**May not:** run indefinitely; hide failed attempts; repeatedly inspect the
locked test; alter trial counts; promote a candidate solely for exceeding a
Sharpe threshold; send signals to Geld; modify Geld; place trades.

**Budgets** (already enforced by `registry.holdout.ResearchBudget` /
`HoldoutGovernor`): max candidates per family, max holdout accesses, max
mutations per lineage. Compute/task-count budgets are added when the loop is
wired.

The building blocks (generators, registry, budgets, decision function, reporting)
all exist today; Phase B composes them into an autonomous loop. See
[ROADMAP.md](ROADMAP.md).
