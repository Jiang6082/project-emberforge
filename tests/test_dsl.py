import pytest

from emberforge.dsl import (
    CausalityError,
    ValidationError,
    canonical_string,
    factor_hash,
    make_factor,
    parse,
)
from emberforge.dsl.parser import ParseError


def test_parse_function_and_arithmetic():
    tree = parse("add(ts_returns(close,5), 1)")
    assert canonical_string(tree) == "add(1,ts_returns(close,5))"


def test_binary_operators_desugar():
    assert canonical_string(parse("close + close")) == "add(close,close)"
    assert canonical_string(parse("close - open")) == "subtract(close,open)"
    assert canonical_string(parse("-close")) == "neg(close)"


def test_canonicalization_sorts_commutative():
    a = parse("add(close, volume)")
    b = parse("add(volume, close)")
    assert canonical_string(a) == canonical_string(b)
    assert factor_hash(a) == factor_hash(b)


def test_noncommutative_not_reordered():
    assert factor_hash(parse("subtract(close, open)")) != factor_hash(parse("subtract(open, close)"))


def test_hash_stable_and_short():
    h = factor_hash(parse("ts_mean(close, 10)"))
    assert isinstance(h, str) and len(h) == 32


def test_unknown_field_rejected():
    with pytest.raises(ParseError):
        parse("foobar")


def test_unknown_operator_rejected():
    with pytest.raises(ValidationError):
        make_factor("x", "not_an_op(close, 5)")


def test_wrong_arity_rejected():
    with pytest.raises(ValidationError):
        make_factor("x", "ts_mean(close)")


def test_negative_lag_is_lookahead():
    with pytest.raises(CausalityError):
        make_factor("x", "ts_delay(close, -1)")


def test_zero_window_rejected():
    with pytest.raises(CausalityError):
        make_factor("x", "ts_mean(close, 0)")


def test_non_integer_window_rejected():
    with pytest.raises(CausalityError):
        make_factor("x", "ts_mean(close, 5.5)")


def test_forbidden_future_operator():
    with pytest.raises((ValidationError, CausalityError, ValueError)):
        make_factor("x", "future_return(close, 1)")


def test_complexity_limit():
    deep = "close"
    for _ in range(12):
        deep = f"ts_mean({deep}, 2)"
    with pytest.raises(ValidationError):
        make_factor("deep", deep)


def test_factorspec_derived_fields():
    spec = make_factor("m", "ts_returns(close, 20)", expected_sign=1)
    assert spec.required_fields == ("close",)
    assert spec.max_lookback == 20
    assert spec.complexity_score > 0
    assert spec.expression_hash
