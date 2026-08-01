"""The end-to-end demo is itself an acceptance test."""

from emberforge.demo import run_demo

import pytest

pytestmark = pytest.mark.slow



def test_demo_runs_end_to_end(tmp_path):
    summary = run_demo(out_dir=tmp_path / "demo")

    # every candidate is recorded, including failures and duplicates
    assert summary["n_recorded_experiments"] >= summary["n_candidates"]
    assert summary["n_candidates"] >= 6

    # the real momentum factor should survive; noise should not
    assert "momentum_20" in summary["survivors"]
    assert "noise_1bar" not in summary["survivors"]

    # something was rejected or flagged duplicate (failures stay visible)
    assert summary["rejected"] or summary["duplicates"]

    # a checksummed, human-approved bundle was exported
    assert summary["exported"] is not None
    assert summary["exported"]["checksums_ok"] is True


def test_demo_records_failures_not_just_winner(tmp_path):
    from emberforge.registry import ExperimentRegistry

    out = tmp_path / "demo"
    run_demo(out_dir=out)
    reg = ExperimentRegistry(out / "registry.sqlite3")
    rows = reg.list(family="momentum_family")
    statuses = {r["status"] for r in rows}
    # more than one outcome means the losers were kept
    assert len(statuses) > 1
    assert any("reject" in s or s == "duplicate" for s in statuses)
