# Emberforge ↔ Geld: who does what

A short architecture note on where the boundary between the two projects sits,
and why.

## Three layers, two projects

Turning an idea into a trade has three layers:

| Layer | Question it answers | Owner |
|---|---|---|
| **Signal** | *What predicts returns?* (a factor: "rank stocks by 20-day momentum") | **Emberforge** |
| **Portfolio** | *How do I turn predictions into positions?* (sizing, entry/exit, rebalancing) | **shared** — Emberforge *recommends*, Geld *decides* |
| **Execution** | *How do I place & manage real orders safely?* (fills, reconciliation, risk, accounts) | **Geld** |

- **Emberforge is the research lab.** It discovers factors, proves them with
  selection-bias-aware statistics, and runs a *research* backtest. It never trades.
- **Geld is the trading desk.** It runs strategies on Alpaca paper money, with
  reconciliation, risk gates, per-strategy virtual accounts, and safety locks.

## Two kinds of backtest — not redundant

Both projects "backtest," but they answer different questions:

| | Emberforge's backtest | Geld's backtest |
|---|---|---|
| Kind | **research / statistical** | **execution / realism** |
| Measures | IC, decay, Deflated Sharpe, PBO, walk-forward, cross-sectional net-of-cost equity | next-bar fills, transaction costs, per-symbol round-trips |
| Purpose | *Is there a real edge?* | *Can I actually capture it?* |

An idea should survive **both** — that's two independent checkpoints, and the
second one lives in Geld on purpose.

## Why the split is a feature, not a limitation

The system that *searches* for edges can fool itself (that's Emberforge's whole
reason for existing — the anti-self-deception machinery). Firewalling it from the
system that *moves money* means a research bug can never place a trade. So:

- Emberforge **may**: propose factors, prove them, recommend a portfolio
  construction, export an approved bundle.
- Emberforge **may not**: place orders, decide live position sizing, or push
  anything into Geld's runtime. The only thing that crosses the boundary is a
  **manual, offline, validated bundle file**.

## What was added to keep Emberforge in its lane while being more useful

- A **portfolio-construction hint** (`analytics.portfolio_backtest.PortfolioSpec`)
  and a **portfolio-level research backtest** — so the exported recipe is
  position-aware (net Sharpe, drawdown), without Emberforge running orders.
- A **schema adapter** (`export.geld_bundle`) that maps an Emberforge candidate
  onto Geld's `candidate_bundle_v1` contract, so the hand-off actually validates
  on Geld's side. Emberforge still never imports Geld.

## The hand-off, end to end

```
Emberforge:  hypothesis → factor → prove → research backtest → approved bundle
                                                                     │  (manual, offline file)
                                                                     ▼
Geld:        import → validate → quarantine → [human/executor decides] → (its own execution backtest) → paper trade
```

Emberforge stops at the **approved, position-aware recipe**. Geld remains the sole
executor and the last line of defense — an idea still has to clear Geld's
realistic backtest and safety gates before any paper order is placed.
