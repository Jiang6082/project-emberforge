import numpy as np

from emberforge.stats import (
    benjamini_hochberg,
    circular_block_bootstrap,
    deflated_sharpe,
    expected_max_sharpe,
    holm,
    ic_pvalue,
    pbo_cscv,
)


def test_bh_monotone_and_bounds():
    p = [0.001, 0.02, 0.03, 0.5, 0.9]
    adj = benjamini_hochberg(p)
    vals = [a.p_adjusted for a in adj]
    assert all(0 <= v <= 1 for v in vals)
    assert adj[0].reject and not adj[-1].reject


def test_holm_more_conservative_than_bh():
    p = [0.01, 0.02, 0.04, 0.2]
    bh = benjamini_hochberg(p)
    hl = holm(p)
    assert all(h.p_adjusted >= b.p_adjusted - 1e-9 for h, b in zip(hl, bh))


def test_expected_max_sharpe_grows_with_trials():
    assert expected_max_sharpe(100, 0.5) > expected_max_sharpe(2, 0.5)


def test_deflated_sharpe_penalizes_more_trials():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 500)
    few = deflated_sharpe(r, n_trials=1, sr_variance=0.01).dsr
    many = deflated_sharpe(r, n_trials=1000, sr_variance=0.01).dsr
    assert many <= few


def test_pbo_in_unit_interval():
    rng = np.random.default_rng(1)
    M = rng.normal(0, 0.01, size=(200, 6))
    res = pbo_cscv(M, n_splits=8)
    assert 0.0 <= res.pbo <= 1.0


def test_pbo_high_for_pure_noise():
    rng = np.random.default_rng(2)
    M = rng.normal(0, 0.01, size=(240, 8))
    # pure noise: the IS-best should not persist OOS -> PBO not tiny
    assert pbo_cscv(M, n_splits=8).pbo >= 0.3


def test_bootstrap_ci_contains_point():
    rng = np.random.default_rng(3)
    r = rng.normal(0.001, 0.01, 300)
    ci = circular_block_bootstrap(r, statistic="mean", seed=0)
    assert ci.lower <= ci.point <= ci.upper


def test_ic_pvalue_small_for_large_t():
    assert ic_pvalue(5.0, 200) < 0.01
    assert ic_pvalue(0.1, 200) > 0.5
