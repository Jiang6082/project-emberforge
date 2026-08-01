# Multiple Testing & Overfitting Controls

No single method here is treated as proof of alpha. Each states its assumptions,
and reports show raw metrics separately from adjusted evidence.

## Implemented (v1)

### Benjamini–Hochberg FDR — `stats.benjamini_hochberg`
Step-up control of the false-discovery rate across a family's p-values (from the
IC t-statistics). Adjusted p-values are monotone and clipped to `[0, 1]`.

### Holm–Bonferroni — `stats.holm`
Step-down control of the family-wise error rate; strictly more conservative than
BH. Used as a sanity ceiling.

### Deflated Sharpe Ratio — `stats.deflated_sharpe`
Implements Bailey & López de Prado (2014). Discounts an observed Sharpe for:
* **trial count** — via the expected maximum Sharpe of `N` null strategies,
  `SR₀ = √Var(SR)·[(1−γ)·Z⁻¹(1−1/N) + γ·Z⁻¹(1−1/(N·e))]`;
* **non-normality & length** — the Sharpe estimator's standard error uses sample
  skewness and kurtosis over `T` observations.

`DSR = Φ((SR − SR₀) / σ_SR)`. The trial count `N` comes from the registry's
family counter; `Var(SR)` is estimated from the family's per-period Sharpes.

### Probability of Backtest Overfitting — `stats.pbo_cscv`
Combinatorially-Symmetric Cross-Validation (Bailey et al. 2017), documented as an
approximation. Input is a `T × N_strategies` matrix of diagnostic long-short
returns. The `T` rows are cut into `S` (even) blocks; over every split of `S/2`
in-sample vs out-of-sample blocks, it checks whether the in-sample-best strategy
keeps up out-of-sample. PBO is the fraction of splits where it does not — high
PBO means the *selection process itself* is overfit.

### Block bootstrap — `stats.circular_block_bootstrap`
Circular block resampling preserves short-horizon autocorrelation, giving honest
confidence intervals for serially-correlated series (daily returns, IC series).

## The DSR / PBO input bridge

Deflated Sharpe and PBO both consume the **diagnostic long-short portfolio's
per-period return series** — the top-minus-bottom quantile spread built by
`analytics.portfolio.long_short_returns`. This is the Sharpe being deflated. The
diagnostic portfolio is explicitly **not executable**; it is a summary statistic.

## How the pipeline uses them

For a family study (`research.pipeline.run_family_study`):
1. record every experiment → fix the trial count `N`;
2. BH + Holm across the family's IC p-values;
3. PBO across the aligned family return matrix;
4. per candidate: Deflated Sharpe (with `N` and family `Var(SR)`) + bootstrap CI;
5. the decision function requires FDR survival **and** `DSR ≥ threshold` **and**
   novelty — a high Sharpe alone never promotes.

## Extension points (design-only in v1)

White's Reality Check, Hansen's SPA, combinatorial *purged* cross-validation, and
embargoed cross-validation. See [ROADMAP.md](ROADMAP.md).
