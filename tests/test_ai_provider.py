"""AnthropicProvider is tested fully offline via a fake client — no network."""

import json
import types

import pytest

from emberforge.generate import AISchemaError, AnthropicProvider, generate_ai


def _fake_response(text, stop_reason="end_turn"):
    block = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(content=[block], stop_reason=stop_reason)


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def test_provider_returns_json_and_builds_factor():
    payload = json.dumps({
        "factor_id": "ai_mom_12", "expression": "ts_returns(close,12)",
        "economic_hypothesis": "12-bar momentum.", "expected_sign": 1,
        "required_fields": ["close"],
    })
    client = _FakeClient(_fake_response(payload))
    provider = AnthropicProvider(model="claude-opus-5", client=client)
    spec = generate_ai("underexplored: momentum", provider=provider)
    assert spec.expression_hash
    assert spec.generator == "ai"
    # it used structured output (json_schema format) on the real API surface
    assert client.messages.calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert client.messages.calls[0]["model"] == "claude-opus-5"


def test_provider_handles_refusal():
    client = _FakeClient(_fake_response("", stop_reason="refusal"))
    provider = AnthropicProvider(client=client)
    with pytest.raises(AISchemaError):
        provider.complete("anything")


def test_provider_invalid_expression_still_rejected():
    payload = json.dumps({
        "factor_id": "leaky", "expression": "ts_delay(close,-1)",
        "economic_hypothesis": "peeks ahead", "expected_sign": 1,
        "required_fields": ["close"],
    })
    provider = AnthropicProvider(client=_FakeClient(_fake_response(payload)))
    with pytest.raises(Exception):
        generate_ai("x", provider=provider)


def test_default_model_is_opus_5():
    assert AnthropicProvider().model == "claude-opus-5"
