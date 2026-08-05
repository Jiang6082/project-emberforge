"""Cross-check the FDR/FWER corrections against an independent reference.

Emberforge implements Benjamini-Hochberg and Holm from scratch (small, dependency-
light, and easy to audit). Because these corrections *are* the significance bar,
a subtle off-by-one in a rank multiplier or a missing monotonicity step would
quietly let under-penalized factors through. statsmodels is already a dependency,
so we use its long-established ``multipletests`` as an oracle: adjusted p-values
must match to floating-point tolerance and the reject decisions must be identical,
across many random p-value vectors including ties and exact 0/1 endpoints.
"""

from __future__ import annotations

import numpy as np
import pytest
from statsmodels.stats.multitest import multipletests

from emberforge.stats import benjamini_hochberg, holm

ALPHA = 0.05


def _vectors():
    rng = np.random.default_rng(20240804)
    for trial in range(120):
        m = int(rng.integers(1, 25))
        p = rng.random(m)
        if trial % 6 == 0 and m > 2:
            p[0], p[1], p[2] = 0.0, 1.0, p[1]  # endpoints + a tie
        yield p


@pytest.mark.parametrize("method,ef_fn", [("fdr_bh", benjamini_hochberg), ("holm", holm)])
def test_matches_statsmodels(method, ef_fn):
    worst = 0.0
    for p in _vectors():
        ef = ef_fn(list(p), alpha=ALPHA)
        ef_adj = np.array([a.p_adjusted for a in ef])
        ef_rej = [a.reject for a in ef]
        sm_rej, sm_adj, *_ = multipletests(p, alpha=ALPHA, method=method)
        worst = max(worst, float(np.max(np.abs(ef_adj - sm_adj))))
        assert ef_rej == list(sm_rej), f"{method}: reject decisions diverge for {p}"
    assert worst < 1e-12, f"{method}: adjusted p-values diverge from statsmodels by {worst}"
