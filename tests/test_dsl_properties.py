"""Property-based tests for the factor DSL (Hypothesis).

The DSL is the most safety-critical component — parse/canonicalize/hash and the
causality guarantees underpin everything downstream. Instead of a handful of
hand-picked expressions, these tests generate thousands of random *valid* trees
and assert the invariants hold for all of them:

* an expression round-trips through ``to_string -> parse`` with identical
  canonical form and hash;
* canonicalization is idempotent;
* every structurally-valid tree with positive integer windows passes causality;
* commutative operators hash independently of argument order;
* any negative/zero window is rejected as look-ahead.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from emberforge.dsl import (
    CausalityError,
    canonical_string,
    causality,
    factor_hash,
    operators,
    parse,
    to_string,
)
from emberforge.dsl.nodes import RAW_FIELDS, Call, Const, Field, depth, node_count

FIELDS = sorted(RAW_FIELDS)
OPS = list(operators.REGISTRY.items())
# 2-arg time-series operators whose window is argument index 1
TS_WINDOW_OPS = [n for n, s in OPS if s.arity == 2 and s.window_args == (1,)]

_leaves = st.one_of(
    st.sampled_from(FIELDS).map(Field),
    st.integers(min_value=1, max_value=250).map(lambda n: Const(float(n))),
)


def _extend(children):
    branches = []
    for name, spec in OPS:
        arg_strats = [
            st.integers(1, 60).map(lambda n: Const(float(n))) if i in spec.window_args else children
            for i in range(spec.arity)
        ]
        branches.append(st.tuples(*arg_strats).map(lambda args, _n=name: Call(_n, tuple(args))))
    return st.one_of(branches)


# valid trees, bounded to the DSL's structural limits so causality.validate applies
trees = st.recursive(_leaves, _extend, max_leaves=8).filter(
    lambda t: depth(t) <= 8 and node_count(t) <= 40
)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(trees)
def test_parse_roundtrip_preserves_canonical_and_hash(tree):
    s = to_string(tree)
    reparsed = parse(s)
    assert canonical_string(reparsed) == canonical_string(tree)
    assert factor_hash(reparsed) == factor_hash(tree)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(trees)
def test_canonicalization_is_idempotent(tree):
    c = canonical_string(tree)
    assert canonical_string(parse(c)) == c


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(trees)
def test_valid_trees_pass_causality(tree):
    causality.validate(tree)  # must not raise: valid ops, arity, positive windows


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(a=trees, b=trees, op=st.sampled_from(["add", "multiply", "min", "max"]))
def test_commutative_operators_hash_regardless_of_order(a, b, op):
    assert factor_hash(Call(op, (a, b))) == factor_hash(Call(op, (b, a)))


@settings(max_examples=100, deadline=None)
@given(op=st.sampled_from(TS_WINDOW_OPS), n=st.integers(min_value=-60, max_value=0))
def test_nonpositive_window_is_rejected_as_lookahead(op, n):
    node = Call(op, (Field("close"), Const(float(n))))
    with pytest.raises(CausalityError):
        causality.check_causality(node)
