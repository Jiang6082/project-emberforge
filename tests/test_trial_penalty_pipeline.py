"""The trial count must actually raise the significance bar — end to end.

The whole anti-self-deception premise is that trying many factors makes any one
winner *less* surprising, so its bar rises with the number of attempts. The unit
test ``test_deflated_sharpe_penalizes_more_trials`` proves the DSR math has that
property in isolation; this proves the *live pipeline* honours it — that
``registry.family_trial_count`` genuinely flows into the Deflated Sharpe gate.

If someone regressed the wiring (hardcoded ``n_trials=1``, dropped the argument,
counted the wrong thing), the identical factor on identical data would score the
same DSR regardless of how many trials the family had logged, and this test fails.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from emberforge.dsl import make_factor
from emberforge.registry import ExperimentRegistry
from emberforge.research import run_family_study

FAMILY = "penalty_fam"


def _preseed_trials(reg: ExperimentRegistry, n: int) -> None:
    """Insert ``n`` minimal recorded trials in FAMILY so family_trial_count rises,
    without running that many real evaluations. Uses one connection for speed."""
    now = datetime.now(UTC).isoformat()
    rows = [
        (f"seed{i:05d}", FAMILY, f"f{i}", "ts_returns(close,10)", "h", now, "evaluated")
        for i in range(n)
    ]
    con = sqlite3.connect(reg.path)
    try:
        con.executemany(
            "INSERT INTO experiments "
            "(experiment_id, family, factor_id, expression, expression_hash, created_at, status) "
            "VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def _dsr_for(data, tmp_path, name, preseed: int) -> tuple[float, int]:
    reg = ExperimentRegistry(tmp_path / f"{name}.sqlite3")
    if preseed:
        _preseed_trials(reg, preseed)
    spec = make_factor("mom", "ts_returns(close, 10)")
    study = run_family_study(FAMILY, [spec], data, reg, seed=1)
    rep = study.results[0].report
    return rep["statistics"]["dsr"], rep["trial_count"]


@pytest.mark.slow
def test_more_family_trials_lower_the_deflated_sharpe(small_data, tmp_path):
    dsr_few, trials_few = _dsr_for(small_data, tmp_path, "few", preseed=0)
    dsr_many, trials_many = _dsr_for(small_data, tmp_path, "many", preseed=1500)

    # Same factor, same data — only the number of logged trials differs.
    assert trials_many > trials_few
    assert dsr_few == dsr_few and dsr_many == dsr_many  # both are real numbers, not NaN
    # A thousand-plus prior attempts must make this exact result strictly less
    # convincing. Equality (or an increase) would mean the trial count never
    # reached the significance bar.
    assert dsr_many < dsr_few
