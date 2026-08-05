"""New causal operators and the factor families built on them.

Each operator is verified for numeric correctness (against a direct pandas
computation), causality (the perturbation detector must accept it), and its role
in a new template family that flows through the research pipeline and is
classified into the right economic family for dedup.
"""

from __future__ import annotations

import numpy as np
import pytest

from emberforge.compute import assert_no_lookahead, evaluate
from emberforge.dedup.semantic import classify
from emberforge.dsl import make_factor
from emberforge.generate.templates import TEMPLATES, generate_templates
from emberforge.registry import ExperimentRegistry
from emberforge.research import run_family_study

NEW_OPS = ["ts_sum", "ts_skew", "ts_zscore", "ts_argmax", "ts_argmin"]


@pytest.mark.parametrize("expr", [
    "ts_sum(close,5)",
    "ts_skew(ts_returns(close,1),20)",
    "ts_zscore(close,15)",
    "ts_argmax(close,10)",
    "ts_argmin(close,10)",
])
def test_new_operators_are_causal(expr, data):
    assert_no_lookahead(make_factor("t", expr), data)  # must not raise


def test_ts_sum_matches_pandas(data):
    got = evaluate(make_factor("t", "ts_sum(close,5)").tree(), data)
    exp = data.field("close").rolling(5, min_periods=5).sum()
    assert np.allclose(got.dropna().values, exp.dropna().values)


def test_ts_zscore_matches_pandas(data):
    got = evaluate(make_factor("t", "ts_zscore(close,15)").tree(), data)
    close = data.field("close")
    roll = close.rolling(15, min_periods=15)
    exp = (close - roll.mean()) / roll.std().replace(0.0, np.nan)
    assert np.allclose(got.dropna().values, exp.dropna().values, equal_nan=True)


def test_ts_argmax_counts_bars_since_high():
    # A strictly increasing series is always at its high -> 0 bars since max;
    # a strictly decreasing series' max is n-1 bars back.
    from emberforge.data import make_synthetic
    from emberforge.data.schema import MarketData

    d = make_synthetic(n_symbols=4, n_days=40, seed=1)
    import pandas as pd
    up = pd.DataFrame({s: np.arange(40.0) for s in d.symbols}, index=d.index)
    down = pd.DataFrame({s: np.arange(40.0)[::-1] for s in d.symbols}, index=d.index)
    amx = evaluate(make_factor("t", "ts_argmax(close,10)").tree(), MarketData({**d.panels, "close": up}, d.metadata))
    amn = evaluate(make_factor("t", "ts_argmax(close,10)").tree(), MarketData({**d.panels, "close": down}, d.metadata))
    assert float(amx.iloc[-1].iloc[0]) == 0.0     # increasing: high is now
    assert float(amn.iloc[-1].iloc[0]) == 9.0      # decreasing: high is 9 bars back


@pytest.mark.parametrize("name,family", [
    ("skewness", "skewness"),
    ("mean_reversion", "reversal"),
    ("high_proximity", "trend"),
])
def test_new_templates_classify_into_expected_family(name, family):
    expr_tmpl = TEMPLATES[name][0]
    spec = make_factor(name, expr_tmpl.format(w=20))
    assert classify(spec) == family


def test_new_families_flow_through_pipeline(small_data, tmp_path):
    specs = generate_templates(horizons=(10, 20), which=["skewness", "mean_reversion", "high_proximity"])
    assert len(specs) == 6  # 3 families x 2 horizons, all valid
    reg = ExperimentRegistry(tmp_path / "reg.sqlite3")
    study = run_family_study("new_fam", specs, small_data, reg, seed=1)
    # every candidate was evaluated (none rejected as invalid / leaking)
    assert {r.spec.factor_id for r in study.results} == {s.factor_id for s in specs}
    assert not reg.list(family="new_fam", status="invalid")
