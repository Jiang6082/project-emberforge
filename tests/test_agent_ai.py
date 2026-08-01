"""The agent's AI generation path is exercised offline via the MockProvider."""

from emberforge.agent import ResearchAgent
from emberforge.data import make_synthetic
from emberforge.generate import MockProvider
from emberforge.registry import ExperimentRegistry
from emberforge.registry.holdout import ResearchBudget

import pytest

pytestmark = pytest.mark.slow



def _agent(tmp_path, provider, seed=7):
    data = make_synthetic(n_symbols=12, n_days=300, seed=seed)
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    return ResearchAgent(data, reg, budget=ResearchBudget(max_candidates=40),
                         seed=seed, ai_provider=provider), reg


def test_agent_includes_ai_candidates(tmp_path):
    agent, reg = _agent(tmp_path, MockProvider())
    report = agent.run(families=["momentum"])
    rows = reg.list(family="momentum")
    generators = {r["generator"] for r in rows}
    assert "ai" in generators  # the mock provider's candidates were recorded


def test_agent_without_provider_has_no_ai(tmp_path):
    agent, reg = _agent(tmp_path, None)
    agent.run(families=["momentum"])
    rows = reg.list(family="momentum")
    assert "ai" not in {r["generator"] for r in rows}


def test_ai_candidates_still_go_through_validation(tmp_path):
    # a provider that emits a look-ahead expression must not produce an experiment
    import json
    import types

    class LeakyProvider:
        model = "leaky"

        def complete(self, prompt):
            return json.dumps({
                "factor_id": "leak", "expression": "ts_delay(close,-1)",
                "economic_hypothesis": "peeks", "expected_sign": 1,
                "required_fields": ["close"],
            })

    agent, reg = _agent(tmp_path, LeakyProvider())
    agent.run(families=["volatility"])
    rows = reg.list(family="volatility")
    # the leaky AI expression was rejected before ever becoming an experiment
    assert all(r["expression"] != "ts_delay(close,-1)" for r in rows)


def test_agent_ai_respects_budget(tmp_path):
    data = make_synthetic(n_symbols=12, n_days=300, seed=7)
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    agent = ResearchAgent(data, reg, budget=ResearchBudget(max_candidates=3),
                          seed=7, ai_provider=MockProvider())
    report = agent.run(families=["momentum"])
    assert report.n_candidates_evaluated <= 3
