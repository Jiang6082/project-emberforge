"""Transaction-cost and capacity modelling beyond a flat bps proxy.

The per-period cost of running the diagnostic long-short portfolio at assets
under management ``aum`` decomposes into:

* **commission** — a flat bps on traded notional;
* **half-spread** — bps on traded notional (crossing the bid/ask);
* **market impact** — a concave function of participation rate,
  ``impact_coef · sqrt(participation)``, so impact grows with AUM;
* **borrow** — an annualized bps on the short leg, charged every period.

``participation`` is the traded notional per name divided by that name's average
daily dollar volume (ADV). Because impact scales with ``sqrt(aum)``, there is a
finite **capacity** — the AUM at which net alpha hits zero. All of this is a
research approximation; it is not an execution model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TRADING_DAYS = 252


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 1.0        # per unit one-way turnover
    half_spread_bps: float = 2.0       # per unit one-way turnover
    impact_coef: float = 0.1           # impact (fraction) = coef * sqrt(participation)
    borrow_bps_annual: float = 50.0    # short-borrow, annualized
    has_short_leg: bool = True

    def per_period_cost(self, turnover: float, participation: float = 0.0) -> float:
        """Per-period cost as a return fraction, given one-way ``turnover`` and
        the fraction of ADV traded (``participation``)."""
        turnover = max(0.0, float(turnover))
        linear = (self.commission_bps + self.half_spread_bps) / 1e4 * turnover
        impact = self.impact_coef * np.sqrt(max(participation, 0.0)) * turnover
        borrow = (self.borrow_bps_annual / 1e4) / TRADING_DAYS if self.has_short_leg else 0.0
        return float(linear + impact + borrow)


@dataclass(frozen=True)
class CapacityEstimate:
    capacity_usd: float
    gross_alpha_per_period: float
    adv_usd: float
    n_positions: int
    note: str = ""


def _participation(aum: float, turnover: float, n_positions: int, adv_usd: float) -> float:
    if adv_usd <= 0 or n_positions <= 0:
        return float("inf")
    traded_per_name = turnover * aum / n_positions
    return traded_per_name / adv_usd


def estimate_capacity(
    gross_alpha_per_period: float,
    adv_usd: float,
    turnover: float,
    n_positions: int,
    model: CostModel = CostModel(),
) -> CapacityEstimate:
    """AUM at which per-period cost erodes the gross alpha to zero.

    Solves ``gross_alpha = per_period_cost(aum)`` for AUM by bisection (cost is
    monotone increasing in AUM through the impact term).
    """
    if not np.isfinite(gross_alpha_per_period) or gross_alpha_per_period <= 0:
        return CapacityEstimate(0.0, gross_alpha_per_period, adv_usd, n_positions,
                                "no positive gross alpha to deploy")
    fixed = model.per_period_cost(turnover, participation=0.0)
    if fixed >= gross_alpha_per_period:
        return CapacityEstimate(0.0, gross_alpha_per_period, adv_usd, n_positions,
                                "fixed costs already exceed gross alpha")

    def net(aum: float) -> float:
        part = _participation(aum, turnover, n_positions, adv_usd)
        return gross_alpha_per_period - model.per_period_cost(turnover, part)

    lo, hi = 0.0, 1e6
    # expand upper bound until net(hi) < 0
    for _ in range(60):
        if net(hi) < 0:
            break
        hi *= 2
    else:
        return CapacityEstimate(float("inf"), gross_alpha_per_period, adv_usd, n_positions,
                                "capacity exceeds search bound")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if net(mid) >= 0:
            lo = mid
        else:
            hi = mid
    return CapacityEstimate(float(0.5 * (lo + hi)), gross_alpha_per_period, adv_usd, n_positions)


def cost_sensitivity(gross_sharpe: float, gross_alpha_per_period: float, ann_vol: float,
                     turnover: float, cost_bps_levels=(0.0, 5.0, 10.0, 20.0)) -> dict[float, float]:
    """Annualized Sharpe after a flat per-turnover cost at several bps levels —
    a quick read on how fragile the edge is to costs."""
    out: dict[float, float] = {}
    if ann_vol <= 0 or not np.isfinite(ann_vol):
        return {b: float("nan") for b in cost_bps_levels}
    for b in cost_bps_levels:
        cost = (b / 1e4) * max(turnover, 0.0)
        net_ann_return = (gross_alpha_per_period - cost) * TRADING_DAYS
        out[b] = float(net_ann_return / ann_vol)
    return out


__all__ = ["CostModel", "CapacityEstimate", "estimate_capacity", "cost_sensitivity"]
