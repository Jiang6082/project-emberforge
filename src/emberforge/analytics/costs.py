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
    impact_coef: float = 0.1           # square-root impact coefficient
    borrow_bps_annual: float = 50.0    # short-borrow, annualized
    has_short_leg: bool = True
    default_daily_vol: float = 0.02    # used when a per-name vol isn't supplied

    def per_period_cost(self, turnover: float, participation: float = 0.0,
                        daily_vol: float | None = None) -> float:
        """Per-period cost as a return fraction.

        Impact follows an Almgren-style square-root law scaled by the name's
        daily volatility: ``impact ≈ impact_coef · σ · sqrt(participation)``.
        When ``daily_vol`` is None a default σ is used, recovering the plain
        ``impact_coef · sqrt(participation)`` shape up to that constant.
        """
        turnover = max(0.0, float(turnover))
        sigma = self.default_daily_vol if daily_vol is None else float(daily_vol)
        linear = (self.commission_bps + self.half_spread_bps) / 1e4 * turnover
        impact = self.impact_coef * sigma * np.sqrt(max(participation, 0.0)) * turnover
        borrow = (self.borrow_bps_annual / 1e4) / TRADING_DAYS if self.has_short_leg else 0.0
        return float(linear + impact + borrow)


@dataclass(frozen=True)
class CapacityEstimate:
    capacity_usd: float
    gross_alpha_per_period: float
    adv_usd: float
    n_positions: int
    note: str = ""


def _cost_at_aum(aum, turnover, adv, vol, model) -> float:
    """Total per-period cost at ``aum``, supporting scalar or per-name ADV/vol.

    Per-name ADV lets the least-liquid names dominate impact, which is the whole
    point of a capacity estimate — a portfolio that must trade thin names caps out
    sooner than its median-ADV would suggest.
    """
    adv_arr = np.atleast_1d(np.asarray(adv, dtype=float))
    m = len(adv_arr)
    if vol is None:
        vol_arr = np.full(m, model.default_daily_vol)
    else:
        vol_arr = np.broadcast_to(np.atleast_1d(np.asarray(vol, dtype=float)), (m,))
    fixed_borrow = model.per_period_cost(turnover, participation=0.0)  # impact term is 0 here
    traded_per_name = turnover * aum / m
    with np.errstate(divide="ignore", invalid="ignore"):
        participation = np.where(adv_arr > 0, traded_per_name / adv_arr, np.inf)
    impact = float(np.mean(model.impact_coef * vol_arr * np.sqrt(np.clip(participation, 0, None)) * turnover))
    return fixed_borrow + impact


def estimate_capacity(
    gross_alpha_per_period: float,
    adv_usd,
    turnover: float,
    n_positions: int | None = None,
    model: CostModel = CostModel(),
    daily_vol=None,
) -> CapacityEstimate:
    """AUM at which per-period cost erodes the gross alpha to zero.

    ``adv_usd`` and ``daily_vol`` may be scalars or per-name arrays. With arrays,
    each traded name contributes its own impact (least-liquid names dominate) and
    ``n_positions`` is inferred from the array length. Solved by bisection because
    cost is monotone increasing in AUM through the impact term.
    """
    adv_arr = np.atleast_1d(np.asarray(adv_usd, dtype=float))
    n_pos = len(adv_arr) if adv_arr.size > 1 else (n_positions or 1)
    adv_repr = float(np.nanmedian(adv_arr))

    if not np.isfinite(gross_alpha_per_period) or gross_alpha_per_period <= 0:
        return CapacityEstimate(0.0, gross_alpha_per_period, adv_repr, n_pos,
                                "no positive gross alpha to deploy")
    if adv_arr.size == 1:  # scalar ADV: replicate across n_positions for the mean
        adv_arr = np.full(max(1, n_pos), adv_arr[0])

    fixed = model.per_period_cost(turnover, participation=0.0)
    if fixed >= gross_alpha_per_period:
        return CapacityEstimate(0.0, gross_alpha_per_period, adv_repr, n_pos,
                                "fixed costs already exceed gross alpha")

    def net(aum: float) -> float:
        return gross_alpha_per_period - _cost_at_aum(aum, turnover, adv_arr, daily_vol, model)

    lo, hi = 0.0, 1e6
    for _ in range(60):
        if net(hi) < 0:
            break
        hi *= 2
    else:
        return CapacityEstimate(float("inf"), gross_alpha_per_period, adv_repr, n_pos,
                                "capacity exceeds search bound")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if net(mid) >= 0:
            lo = mid
        else:
            hi = mid
    return CapacityEstimate(float(0.5 * (lo + hi)), gross_alpha_per_period, adv_repr, n_pos)


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
