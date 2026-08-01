import pytest

from emberforge.dsl import make_factor
from emberforge.generate import (
    AISchemaError,
    MockProvider,
    generate_ai,
    generate_templates,
    mutate_family,
    parse_ai_factor,
)


def test_templates_are_deterministic():
    a = [(s.factor_id, s.expression_hash) for s in generate_templates()]
    b = [(s.factor_id, s.expression_hash) for s in generate_templates()]
    assert a == b
    assert len(a) > 0


def test_mutation_changes_window_and_records_parent():
    parent = make_factor("mom", "ts_returns(close, 20)")
    children = mutate_family(parent, windows=(5, 10))
    assert children
    for c in children:
        assert c.parent_ids == ("mom",)
        assert c.expression_hash != parent.expression_hash


def test_ai_mock_produces_valid_factor():
    spec = generate_ai("underexplored: volatility", provider=MockProvider())
    assert spec.expression_hash
    assert spec.generator == "ai"


def test_ai_malformed_json_rejected():
    with pytest.raises(AISchemaError):
        parse_ai_factor("{not json")


def test_ai_missing_keys_rejected():
    with pytest.raises(AISchemaError):
        parse_ai_factor('{"factor_id": "x"}')


def test_ai_invalid_expression_rejected():
    bad = '{"factor_id":"x","expression":"ts_delay(close,-1)","economic_hypothesis":"h","expected_sign":1,"required_fields":["close"]}'
    with pytest.raises(Exception):
        parse_ai_factor(bad)
