# Scientific Method — how Emberforge avoids fooling itself

> "The first principle is that you must not fool yourself — and you are the
> easiest person to fool." — Feynman

Emberforge's purpose is not to maximize an in-sample Sharpe ratio. Given enough
attempts, pure noise will produce an impressive backtest. The platform is built
to make that self-deception *visible and costly*.

## The five failure modes it defends against

### 1. Look-ahead / leakage
A factor that peeks at the future will look brilliant and be worthless.
Defences:
* **Static:** negative/zero windows and "future" operators are rejected at
  validation (`dsl/causality.py`).
* **Dynamic:** `compute.assert_no_lookahead` perturbs future bars and asserts
  that no pre-cut value changes.
* **Structural:** the forward-return *label* is computed by the analytics layer
  and is never a field the DSL can reference.

### 2. Multiple testing / selection bias
Trying many factors inflates the best one's apparent significance. Every
experiment — including failures — is recorded, and the **family trial count**
drives:
* Benjamini–Hochberg and Holm adjustments across the family's p-values;
* the Deflated Sharpe Ratio's expected-maximum penalty;
* PBO across the family's diagnostic return series.

Nothing is deleted for performing poorly; the record of what was tried is what
makes the survivor interpretable.

### 3. Holdout contamination
The locked test can be spent only so many times. Access is recorded, warned, and
(past a hard cap) blocked (`registry/holdout.py`). After the locked test is
viewed, further tuning belongs to a *new experiment generation*, not untouched
validation.

### 4. Overfitting to one regime / parameterization
Promotion (`research/decision.py`) requires stability signals — turnover bounds,
IC t-stat, monotonicity — not just a high Sharpe. Deflated Sharpe and PBO gate
against configurations that only shine in-sample.

### 5. Duplicate rediscovery
Three dedup layers (syntactic hash, empirical correlation, semantic family)
prevent the same idea from being counted as independent evidence.

## The cardinal rule

**A high Sharpe is never sufficient for promotion.** The decision function will
reject a candidate that clears every raw-metric bar if it fails FDR, Deflated
Sharpe, or novelty. No candidate is ever labelled "proven alpha" — the strongest
label is `research_survivor`.

## What the demo demonstrates

Running `python -m emberforge.demo` produces a registry containing ~24
experiments with a spread of outcomes (`research_survivor`, `duplicate`,
`rejected_in_development`, `rejected_after_robustness`). The single survivor is
exported; the failures remain on the record. That asymmetry — many recorded
attempts, one cautiously-promoted survivor — is the whole point.
