from emberforge.agent import ResearchAgent
from emberforge.data import make_synthetic
from emberforge.registry import ExperimentRegistry
from emberforge.registry.holdout import ResearchBudget

import pytest

pytestmark = pytest.mark.slow



def _agent(tmp_path, budget=None, seed=7):
    data = make_synthetic(n_symbols=12, n_days=300, seed=seed)
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    return ResearchAgent(data, reg, budget=budget or ResearchBudget(), seed=seed), reg, data


def test_agent_runs_and_records(tmp_path):
    agent, reg, _ = _agent(tmp_path)
    report = agent.run(families=["momentum"])
    assert report.n_candidates_evaluated > 0
    # everything the agent tried is in the registry
    assert reg.family_trial_count("momentum") >= report.n_candidates_evaluated


def test_agent_never_touches_locked_test(tmp_path):
    agent, reg, _ = _agent(tmp_path)
    report = agent.run(families=["momentum"])
    assert report.holdout_accesses == 0
    assert reg.holdout_access_count("momentum") == 0


def test_agent_respects_candidate_budget(tmp_path):
    agent, reg, _ = _agent(tmp_path, budget=ResearchBudget(max_candidates=3))
    report = agent.run(families=["momentum"])
    assert report.n_candidates_evaluated <= 3


def test_agent_picks_least_explored_family(tmp_path):
    agent, reg, _ = _agent(tmp_path)
    # pre-load the momentum family so the agent should avoid it
    from emberforge.registry import ExperimentRecord

    for i in range(50):
        reg.record(ExperimentRecord(factor_id=f"m{i}", family="momentum",
                                    expression="ts_returns(close,20)", expression_hash=f"h{i}"))
    family, counts = agent.choose_family(["momentum", "volatility"])
    assert family == "volatility"


def test_agent_promotes_via_decision_not_sharpe(tmp_path):
    # survivors must have gone through the multi-gate decision function
    agent, reg, _ = _agent(tmp_path)
    report = agent.run(families=["momentum"])
    for fid in report.survivors:
        row = reg.get(next(r.experiment_id for r in report.study.results if r.spec.factor_id == fid))
        assert row["status"] == "research_survivor"


def test_agent_budget_exhausted_stops_cleanly(tmp_path):
    agent, reg, _ = _agent(tmp_path, budget=ResearchBudget(max_candidates=1))
    # fill the budget first
    from emberforge.registry import ExperimentRecord

    reg.record(ExperimentRecord(factor_id="x", family="momentum",
                                expression="ts_returns(close,20)", expression_hash="h"))
    report = agent.run(families=["momentum"])
    assert report.n_candidates_evaluated == 0
    assert "exhausted" in report.stopped_reason
