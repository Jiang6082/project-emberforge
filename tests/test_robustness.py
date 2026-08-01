import numpy as np

from emberforge.dsl import make_factor
from emberforge.robustness import (
    parameter_sensitivity,
    regime_analysis,
    robustness_report,
    subperiod_stability,
)
from emberforge.stats import purged_embargoed_kfold


def test_momentum_is_subperiod_stable(data):
    s = subperiod_stability(make_factor("m", "ts_returns(close,20)"), data, k=4)
    assert s.sign_consistency >= 0.75
    assert s.stable


def test_noise_is_less_stable(data):
    mom = subperiod_stability(make_factor("m", "ts_returns(close,20)"), data, k=4)
    noise = subperiod_stability(make_factor("n", "ts_returns(close,1)"), data, k=4)
    assert mom.sign_consistency >= noise.sign_consistency


def test_regime_analysis_has_all_regimes(data):
    r = regime_analysis(make_factor("m", "ts_returns(close,20)"), data)
    assert set(r.ic_by_regime) == {"low_vol", "mid_vol", "high_vol"}


def test_parameter_sensitivity_consistent_for_momentum(data):
    ps = parameter_sensitivity("ts_returns(close,{w})", [10, 20, 30, 40], data)
    assert ps.sign_consistency >= 0.75
    assert ps.robust


def test_robustness_report_summary(data):
    rep = robustness_report(
        make_factor("m", "ts_returns(close,20)"), data,
        sensitivity_template="ts_returns(close,{w})", sensitivity_params=[10, 20, 30],
    )
    summary = rep.summary()
    assert "regime_ic" in summary and "passes_robustness" in summary


def test_purged_embargoed_kfold_no_overlap():
    folds = purged_embargoed_kfold(n=100, k=5, horizon=3, embargo=2)
    assert len(folds) == 5
    for f in folds:
        # no training index falls within the purged/embargoed band around the test block
        t0, t1 = f.test[0], f.test[-1]
        band = set(range(t0 - 3, t1 + 3 + 2 + 1))
        assert not (set(f.train.tolist()) & band & set(f.test.tolist()))
        assert not set(f.train.tolist()) & set(f.test.tolist())
