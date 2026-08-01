"""Multiple-testing and overfitting-control statistics.

Extension points (design-only in v1): White's Reality Check, Hansen's SPA,
combinatorial purged cross-validation, embargoed cross-validation. See
``docs/MULTIPLE_TESTING.md``.
"""

from .bootstrap import BootstrapCI, circular_block_bootstrap
from .cv import Fold, purged_embargoed_kfold
from .deflated_sharpe import DSRResult, deflated_sharpe, expected_max_sharpe
from .multiple_testing import Adjusted, benjamini_hochberg, holm
from .pbo import PBOResult, pbo_cscv

__all__ = [
    "benjamini_hochberg", "holm", "Adjusted",
    "deflated_sharpe", "expected_max_sharpe", "DSRResult",
    "pbo_cscv", "PBOResult",
    "circular_block_bootstrap", "BootstrapCI",
    "purged_embargoed_kfold", "Fold",
]


def ic_pvalue(t_stat: float, n: int) -> float:
    """Two-sided p-value for a mean-IC t-statistic (Student-t, n-1 df)."""
    import numpy as np
    from scipy.stats import t as student_t

    if n is None or n < 2 or t_stat is None or np.isnan(t_stat):
        return float("nan")
    return float(2 * student_t.sf(abs(t_stat), df=n - 1))
