"""Causal factor computation.

The engine evaluates a validated expression tree into a timestamp-by-symbol
score matrix, then applies an explicit, ordered preprocessing pipeline
(coverage mask -> winsorize -> normalize -> neutralize -> execution lag). Raw
factor calculation is kept separate from portfolio construction on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data.schema import MarketData
from ..dsl import causality
from ..dsl.nodes import Call, Const, Field, Node
from ..dsl import operators
from ..dsl.spec import FactorSpec


@dataclass(frozen=True)
class PreprocessConfig:
    min_coverage: float = 0.5   # min fraction of non-nan symbols per timestamp
    winsorize_p: float | None = 0.02
    normalize: bool = True       # cross-sectional z-score
    neutralize: bool = False     # cross-sectional demean
    execution_lag: int = 0       # extra bars between signal and application


def _to_node(spec_or_node: FactorSpec | Node) -> Node:
    return spec_or_node.tree() if isinstance(spec_or_node, FactorSpec) else spec_or_node


def evaluate(node: Node, data: MarketData) -> pd.DataFrame:
    """Evaluate a raw expression tree into a score matrix (no preprocessing)."""
    if isinstance(node, Field):
        return data.field(node.name)
    if isinstance(node, Const):
        return node.value  # scalar; pandas broadcasts it in arithmetic ops
    assert isinstance(node, Call)
    spec = operators.get(node.op)
    evaluated = [evaluate(a, data) for a in node.args]
    return spec.fn(*evaluated)


def compute_factor(
    spec_or_node: FactorSpec | Node,
    data: MarketData,
    config: PreprocessConfig = PreprocessConfig(),
    eligibility: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Full causal computation: validate -> evaluate -> (universe mask) -> preprocess.

    ``eligibility`` is an optional point-in-time-safe boolean mask (time x symbol),
    typically produced by ``Universe.eligibility``. Ineligible cells are removed
    *before* cross-sectional normalization, so ranks/z-scores are computed only
    over eligible names.
    """
    node = _to_node(spec_or_node)
    causality.validate(node)
    scores = evaluate(node, data)
    if np.isscalar(scores):
        raise ValueError("factor reduced to a scalar; needs a field somewhere")
    scores = scores.reindex(index=data.index, columns=data.symbols).astype(float)

    if eligibility is not None:
        elig = eligibility.reindex(index=data.index, columns=data.symbols).fillna(False)
        scores = scores.where(elig.astype(bool))

    # coverage mask: drop rows without enough cross-sectional support.
    coverage = scores.notna().mean(axis=1)
    scores = scores.where(coverage >= config.min_coverage)

    if config.winsorize_p:
        lo = scores.quantile(config.winsorize_p, axis=1)
        hi = scores.quantile(1 - config.winsorize_p, axis=1)
        scores = scores.clip(lower=lo, upper=hi, axis=0)
    if config.normalize:
        mu = scores.mean(axis=1)
        sd = scores.std(axis=1).replace(0.0, np.nan)
        scores = scores.sub(mu, axis=0).div(sd, axis=0)
    if config.neutralize:
        scores = scores.sub(scores.mean(axis=1), axis=0)
    if config.execution_lag:
        scores = scores.shift(config.execution_lag)
    return scores


def coverage_series(scores: pd.DataFrame) -> pd.Series:
    return scores.notna().mean(axis=1)


def assert_no_lookahead(
    spec_or_node: FactorSpec | Node, data: MarketData, tol: float = 1e-9, seed: int = 0
) -> None:
    """Data-driven leakage test by *future perturbation*.

    Compute the factor, then perturb every bar strictly after a cut point and
    recompute. A causal factor's values *before* the cut depend only on data at
    or before their own timestamp, so they must be identical. If any pre-cut
    value changes, the factor read the (now-perturbed) future — raise
    :class:`CausalityError`. This reliably catches negative shifts and any other
    forward dependence, which tail-truncation cannot.
    """
    node = _to_node(spec_or_node)
    full = evaluate(node, data)
    if np.isscalar(full):
        return
    n = len(data.index)
    cut = int(n * 0.6)
    rng = np.random.default_rng(seed)
    perturbed_panels = {}
    for name, df in data.panels.items():
        pert = df.copy()
        noise = rng.uniform(1.5, 2.5, size=pert.iloc[cut:].shape)
        pert.iloc[cut:] = pert.iloc[cut:].values * noise
        perturbed_panels[name] = pert
    perturbed = evaluate(node, MarketData(perturbed_panels, data.metadata))

    a = full.iloc[:cut]
    b = perturbed.reindex_like(full).iloc[:cut]
    mask = a.notna() & b.notna()
    diff = (a - b).abs().where(mask)
    worst = float(diff.max().max()) if mask.values.any() else 0.0
    if worst > tol:
        raise causality.CausalityError(
            f"look-ahead detected: pre-cut values changed by up to {worst:.3g} "
            "when future bars were perturbed"
        )
