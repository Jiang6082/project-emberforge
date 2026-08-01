from emberforge.registry import ExperimentRecord, ExperimentRegistry
from emberforge.registry.holdout import (
    BudgetExceeded,
    HoldoutGovernor,
    ResearchBudget,
    split_by_fraction,
)


def _rec(fid, family="fam", parent=None, status="evaluated"):
    return ExperimentRecord(
        factor_id=fid, family=family, expression=f"ts_returns(close,{len(fid)})",
        expression_hash=fid + "hash", status=status, parent_id=parent,
    )


def test_record_and_get(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    eid = reg.record(_rec("a"))
    row = reg.get(eid)
    assert row["factor_id"] == "a"
    assert row["status"] == "evaluated"


def test_failed_experiments_are_retained(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    reg.record(_rec("good", status="research_survivor"))
    reg.record(_rec("bad", status="rejected_in_development"))
    rows = reg.list(family="fam")
    assert {r["factor_id"] for r in rows} == {"good", "bad"}


def test_family_trial_count(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    for i in range(5):
        reg.record(_rec(f"f{i}"))
    assert reg.family_trial_count("fam") == 5


def test_lineage_chain(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    root = reg.record(_rec("root"))
    child = reg.record(_rec("child", parent=root))
    chain = reg.lineage(child)
    assert [c["factor_id"] for c in chain] == ["root", "child"]


def test_holdout_access_tracking(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    eid = reg.record(_rec("a"))
    assert reg.holdout_access_count("fam") == 0
    reg.record_holdout_access("fam", eid, "peek")
    assert reg.holdout_access_count("fam") == 1
    assert reg.get(eid)["holdout_viewed"] == 1


def test_holdout_governor_hard_gate(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    gov = HoldoutGovernor(reg, "fam", ResearchBudget(max_holdout_access=2))
    gov.access_locked_test(None, "1")
    gov.access_locked_test(None, "2")
    try:
        gov.access_locked_test(None, "3")
        assert False, "should have blocked"
    except BudgetExceeded:
        pass


def test_candidate_budget(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    gov = HoldoutGovernor(reg, "fam", ResearchBudget(max_candidates=2))
    reg.record(_rec("a")); reg.record(_rec("b"))
    try:
        gov.check_candidate_budget()
        assert False
    except BudgetExceeded:
        pass


def test_split_by_fraction():
    import pandas as pd

    idx = pd.bdate_range("2021-01-01", periods=100, tz="UTC")
    split = split_by_fraction(idx, 0.6, 0.2)
    assert split.mask(idx, "train").sum() == 60
    assert split.mask(idx, "valid").sum() == 20
    assert split.mask(idx, "test").sum() == 20
