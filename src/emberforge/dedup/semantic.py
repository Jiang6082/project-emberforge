"""Layer 3: semantic / economic classification.

Deterministic, rule-based family assignment from the operators and fields an
expression uses. The AI may *suggest* a family, but this deterministic classifier
and the empirical correlation layer remain the source of truth.
"""

from __future__ import annotations

from ..dsl.nodes import Const, fields_used, ops_used
from ..dsl.spec import FactorSpec

FAMILIES = (
    "momentum", "reversal", "volatility", "liquidity", "volume", "trend",
    "quality", "value", "size", "seasonality", "interaction", "regime", "unknown",
)


def classify(spec: FactorSpec) -> str:
    ops = ops_used(spec.tree())
    fields = fields_used(spec.tree())
    tree = spec.tree()

    # Look for a signed short-horizon return -> reversal.
    def _short_return_negated() -> bool:
        from ..dsl.nodes import Call

        for n in _walk(tree):
            if isinstance(n, Call) and n.op == "neg" and n.args:
                inner = n.args[0]
                if isinstance(inner, Call) and inner.op in {"ts_returns", "ts_delta"}:
                    w = inner.args[1]
                    if isinstance(w, Const) and w.value <= 5:
                        return True
        return False

    if "volume" in fields and {"ts_mean", "cs_rank", "divide"} & ops:
        return "liquidity" if "close" in fields else "volume"
    if {"ts_std", "ts_downside_std"} & ops:
        return "volatility"
    if _short_return_negated():
        return "reversal"
    if {"ts_returns", "ts_delta"} & ops and "close" in fields:
        return "momentum"
    if {"ts_mean", "ts_ewm"} & ops and "close" in fields:
        return "trend"
    if {"ts_corr", "ts_cov"} & ops:
        return "interaction"
    return "unknown"


def _walk(node):
    from ..dsl.nodes import walk

    return walk(node)
