# Cost & Capacity Modelling

`emberforge.analytics.costs` replaces the flat "turnover × bps" proxy with a
transaction-cost decomposition and a capacity estimate. It is a **research
approximation**, not an execution model, and the diagnostic long-short portfolio
it prices is still not an executable strategy.

## The cost decomposition

Per-period cost of running the diagnostic portfolio at assets-under-management
`aum`, as a return fraction:

| Component | Form | Scales with |
|---|---|---|
| Commission | `commission_bps × turnover` | turnover |
| Half-spread | `half_spread_bps × turnover` | turnover |
| Market impact | `impact_coef × σ × √participation × turnover` | √AUM (concave) |
| Borrow | `borrow_bps_annual / 252` (short leg) | time |

`participation` is the traded notional per name divided by that name's average
daily dollar volume (ADV), and `σ` is the name's daily return volatility — an
Almgren-style square-root impact law. Because impact grows with `√participation`
and participation grows with AUM, cost is monotone increasing in AUM.

```python
from emberforge.analytics.costs import CostModel
CostModel().per_period_cost(turnover=0.2, participation=0.01)
```

## Capacity

`estimate_capacity` solves `gross_alpha = per_period_cost(aum)` for AUM by
bisection — the capital at which market impact erodes the gross edge to zero.
It returns `0` when there is no positive gross alpha (or fixed costs already
exceed it) and scales up with ADV (more liquid names support more capital).

`adv_usd` and `daily_vol` accept **per-name arrays**, not just scalars. With
arrays, each traded name contributes its own impact and the least-liquid /
most-volatile names dominate — a portfolio that must trade a thin name caps out
below what its *median* ADV would suggest (verified by
`tests/test_costs.py::test_per_name_adv_least_liquid_dominates`).

`evaluate_factor` builds the per-name ADV (`median(volume × close)` per symbol
over eligible cells) and per-name daily volatility from the dataset, then reports
`capacity_usd` in every candidate report alongside a `cost_sensitivity` curve —
annualized Sharpe at several flat bps levels — so a reviewer can see how fragile
the edge is to costs at a glance.

## Where it shows up

Candidate reports gain two lines:

```
| capacity (USD, impact→0 alpha) | 42000000 |
Cost sensitivity (annualized Sharpe at cost bps): 0.0bps=2.53, 5.0bps=2.43, ...
```

## Limitations

* ADV is a single median snapshot, not a per-name time series.
* Impact is a simple square-root law with one coefficient; it is not calibrated
  to a specific venue or asset class.
* Position count is approximated from the quantile construction.

These are deliberately simple, documented defaults — tune `CostModel` for a real
universe before reading capacity numbers literally.
