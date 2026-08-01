# Factor DSL

A factor is a small, typed expression tree — never arbitrary Python. This keeps
factors parseable, hashable, canonicalizable, and safe to evaluate.

## Node types

* `Field(name)` — a raw field: `open, high, low, close, volume, vwap, returns`.
* `Const(value)` — a numeric literal.
* `Call(op, args)` — an operator applied to child expressions.

## Syntax

Function-call syntax plus arithmetic operators. Examples:

```
ts_returns(close, 20)
neg(ts_std(ts_returns(close, 1), 25))
cs_rank(divide(volume, ts_mean(volume, 20)))
close / ts_mean(close, 50) - 1
```

Binary operators desugar to calls: `a + b → add(a, b)`, `-a → neg(a)`.

## Operators

### Time-series (trailing windows, causal)
`ts_delay, ts_delta, ts_returns, ts_mean, ts_std, ts_min, ts_max, ts_rank,
ts_ewm, ts_corr, ts_cov, ts_downside_std`. The integer window/lag argument must
be a **positive integer literal** — negative or zero is rejected as look-ahead.

### Cross-sectional (within one timestamp)
`cs_rank, cs_percentile, cs_zscore, cs_demean, cs_neutralize, cs_winsor`.

### Arithmetic (elementwise)
`add, subtract, multiply, divide` (safe: ÷0 → NaN), `signed_power, abs, neg,
min, max, clip`.

## Metadata carried by every `FactorSpec`

`factor_id, expression, canonical_expression, expression_hash, description,
economic_hypothesis, required_fields, max_lookback, intended_frequency,
expected_sign, complexity_score, generator, parent_ids, created_at`.

Derived fields (`canonical_expression`, `expression_hash`, `required_fields`,
`max_lookback`, `complexity_score`) are computed and validated at construction —
an invalid factor cannot exist as a `FactorSpec`.

## Canonicalization & hashing

Commutative operators (`add, multiply, min, max`) sort their arguments by
canonical string, so `add(a, b)` and `add(b, a)` produce the **same** hash. This
is the syntactic dedup layer. Hash = first 16 bytes of SHA-256 over the canonical
string.

## Validation pipeline

```
parse → validate_structure (arity, known ops, depth ≤ 8, nodes ≤ 40)
      → check_causality (positive integer windows, no future ops)
      → canonicalize → hash
```

## Safety

* No `eval`; the parser only emits the three node types.
* Unknown identifiers, unknown/forbidden operators, wrong arity, over-complex
  trees, and non-causal windows all raise before evaluation.
* Operator set is closed and explicit — AI generators must emit expressions in
  this DSL, not code.

## CLI

```bash
emberforge factor validate "ts_returns(close, 20)"
emberforge factor evaluate "ts_returns(close, 20)" --horizon 1
emberforge factor compare "ts_returns(close,20)" "ts_delta(close,20)"
```
