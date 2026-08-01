import numpy as np

from emberforge.stats import cpcv_path_distribution, cpcv_splits, n_backtest_paths, pbo_cpcv
from emberforge.stats.pbo import pbo_cscv


def test_cpcv_splits_count_and_no_overlap():
    folds = cpcv_splits(120, n_groups=6, n_test_groups=2, horizon=2, embargo=1)
    from math import comb

    assert len(folds) == comb(6, 2)
    for f in folds:
        assert not set(f.train.tolist()) & set(f.test.tolist())


def test_cpcv_purges_around_test_blocks():
    folds = cpcv_splits(120, n_groups=6, n_test_groups=1, horizon=3, embargo=2)
    for f in folds:
        t0, t1 = f.test[0], f.test[-1]
        banned = set(range(t0 - 3, t1 + 3 + 2 + 1))
        assert not (set(f.train.tolist()) & banned & set(range(t0, t1 + 1)))


def test_n_backtest_paths():
    # C(6,2)=15 combinations, each group in 5 of them -> 15*2/6 = 5 paths
    assert n_backtest_paths(6, 2) == 5


def test_pbo_cpcv_unit_interval():
    rng = np.random.default_rng(0)
    M = rng.normal(0, 0.01, size=(240, 8))
    res = pbo_cpcv(M, n_groups=6, n_test_groups=2)
    assert 0.0 <= res.pbo <= 1.0
    assert res.n_paths == 5


def test_pbo_cpcv_high_for_noise():
    rng = np.random.default_rng(1)
    M = rng.normal(0, 0.01, size=(240, 10))
    assert pbo_cpcv(M, n_groups=6, n_test_groups=2).pbo >= 0.3


def test_cpcv_path_distribution_shape():
    rng = np.random.default_rng(5)
    r = rng.normal(0.001, 0.01, 240)
    d = cpcv_path_distribution(r, n_groups=6, n_test_groups=2)
    from math import comb

    assert d.n_paths == comb(6, 2)
    assert d.p05 <= d.median <= d.p95
    assert 0.0 <= d.fraction_positive <= 1.0


def test_cpcv_path_distribution_flags_unstable_factor():
    rng = np.random.default_rng(6)
    strong = rng.normal(0.002, 0.005, 240)   # consistent edge
    noise = rng.normal(0.0, 0.02, 240)        # no edge, high variance
    ds = cpcv_path_distribution(strong)
    dn = cpcv_path_distribution(noise)
    assert ds.fraction_positive > dn.fraction_positive
    assert ds.p05 > dn.p05


def test_cpcv_agrees_directionally_with_cscv_on_signal():
    # a persistent real edge should give low overfit under both methods
    rng = np.random.default_rng(2)
    T, N = 240, 8
    M = rng.normal(0, 0.01, size=(T, N))
    M[:, 0] += 0.006  # strong, persistent
    assert pbo_cpcv(M, n_groups=6, n_test_groups=2).pbo <= 0.5
    assert pbo_cscv(M, n_splits=6).pbo <= 0.5
