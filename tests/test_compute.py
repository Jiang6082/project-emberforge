import numpy as np
import pytest

from emberforge.compute import assert_no_lookahead, compute_factor, evaluate
from emberforge.compute.engine import PreprocessConfig
from emberforge.dsl import make_factor
from emberforge.dsl.causality import CausalityError


def test_compute_shape(data):
    spec = make_factor("m", "ts_returns(close, 20)")
    scores = compute_factor(spec, data)
    assert scores.shape == (len(data.index), len(data.symbols))


def test_rolling_mean_matches_manual(data):
    close = data.field("close")
    got = evaluate(make_factor("x", "ts_mean(close, 5)").tree(), data)
    expected = close.rolling(5, min_periods=5).mean()
    assert np.allclose(got.dropna().values, expected.dropna().values)


def test_lag_is_past_only(data):
    got = evaluate(make_factor("x", "ts_delay(close, 1)").tree(), data)
    assert np.allclose(got.iloc[1:].values, data.field("close").iloc[:-1].values, equal_nan=True)


def test_no_lookahead_passes_for_causal_factor(data):
    assert_no_lookahead(make_factor("m", "ts_mean(close, 10)"), data)


def test_no_lookahead_detects_leak(data):
    # Bypass the static validator to construct a genuinely future-peeking node
    # (negative shift). The *data-driven* detector must still catch it.
    from emberforge.dsl.nodes import Call, Const, Field

    leaking = Call("ts_delay", (Field("close"), Const(-1)))
    with pytest.raises(CausalityError):
        assert_no_lookahead(leaking, data)


def test_normalization_zero_mean(data):
    scores = compute_factor(make_factor("m", "ts_returns(close, 10)"), data,
                            PreprocessConfig(normalize=True))
    row = scores.dropna().iloc[10]
    assert abs(row.mean()) < 1e-6


def test_missing_data_coverage_mask():
    from emberforge.data import make_synthetic

    d = make_synthetic(n_symbols=6, n_days=60, seed=1)
    d.panels["close"].iloc[:, :5] = np.nan  # only 1/6 symbols valid -> below coverage
    scores = compute_factor(make_factor("m", "close"), d,
                            PreprocessConfig(min_coverage=0.5, normalize=False, winsorize_p=None))
    assert scores.dropna(how="all").empty or scores.notna().mean(axis=1).max() >= 0.5
