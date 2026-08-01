import numpy as np

from emberforge.stats import hansens_spa, whites_reality_check


def test_reality_check_high_p_for_pure_noise():
    rng = np.random.default_rng(0)
    M = rng.normal(0, 0.01, size=(250, 20))  # 20 useless factors
    res = whites_reality_check(M, n_boot=300, seed=1)
    assert 0.0 <= res.p_value <= 1.0
    assert res.p_value > 0.10  # best-of-noise should not look significant


def test_reality_check_low_p_for_real_signal():
    rng = np.random.default_rng(1)
    M = rng.normal(0, 0.01, size=(250, 20))
    M[:, 3] += 0.004  # one genuinely profitable factor
    res = whites_reality_check(M, n_boot=400, seed=2)
    assert res.p_value < 0.10


def test_spa_in_unit_interval_and_noise_not_significant():
    rng = np.random.default_rng(2)
    M = rng.normal(0, 0.01, size=(250, 15))
    res = hansens_spa(M, n_boot=300, seed=3)
    assert 0.0 <= res.p_value <= 1.0
    assert res.p_value > 0.10


def test_spa_detects_real_signal():
    rng = np.random.default_rng(3)
    M = rng.normal(0, 0.01, size=(250, 15))
    M[:, 0] += 0.005
    res = hansens_spa(M, n_boot=400, seed=4)
    assert res.p_value < 0.10


def test_spa_more_powerful_than_reality_check():
    # SPA down-weights poor models, so it should not be *more* conservative than
    # White's RC when a real signal is buried among many bad models.
    rng = np.random.default_rng(4)
    M = rng.normal(0, 0.01, size=(250, 30))
    M[:, 10] += 0.004
    rc = whites_reality_check(M, n_boot=400, seed=5).p_value
    spa = hansens_spa(M, n_boot=400, seed=5).p_value
    assert spa <= rc + 0.05
