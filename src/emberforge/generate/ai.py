"""AI-assisted generation with a provider abstraction (LLM optional).

The AI emits **structured JSON**, never executable code. Every proposal is
validated against the factor schema before it can become a :class:`FactorSpec`.
The default provider is a deterministic mock so the whole system runs with no API
key and no network. A real LLM provider can be dropped in behind the same
interface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from ..dsl.spec import FactorSpec

REQUIRED_KEYS = {
    "factor_id", "expression", "economic_hypothesis", "expected_sign", "required_fields",
}

PROMPT_TEMPLATE = """You are a quant researcher. Propose ONE cross-sectional equity factor.
Return ONLY JSON with keys: factor_id, expression (Emberforge DSL), description,
economic_hypothesis, causal_explanation, expected_sign (-1|0|1), required_fields,
failure_modes, likely_correlation, why_survives_costs, falsification_tests.
Context: {context}
"""


class LLMProvider(Protocol):
    model: str

    def complete(self, prompt: str) -> str: ...


@dataclass
class MockProvider:
    """Deterministic, offline provider. Cycles through a small idea bank."""

    model: str = "mock-1"
    _bank = (
        {"factor_id": "ai_mom_15", "expression": "ts_returns(close,15)",
         "economic_hypothesis": "15-bar momentum persists.", "expected_sign": 1,
         "required_fields": ["close"], "description": "AI momentum idea"},
        {"factor_id": "ai_lowvol", "expression": "neg(ts_std(ts_returns(close,1),25))",
         "economic_hypothesis": "Low-vol names outperform.", "expected_sign": 1,
         "required_fields": ["close"], "description": "AI low-vol idea"},
    )

    def complete(self, prompt: str) -> str:
        idx = int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % len(self._bank)
        return json.dumps(self._bank[idx])


class AISchemaError(ValueError):
    pass


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def parse_ai_factor(raw: str, generator: str = "ai", llm_model: str = "mock-1") -> FactorSpec:
    """Validate raw LLM JSON and turn it into a FactorSpec (or raise)."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AISchemaError(f"AI output is not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise AISchemaError("AI output must be a JSON object")
    missing = REQUIRED_KEYS - obj.keys()
    if missing:
        raise AISchemaError(f"AI output missing required keys: {sorted(missing)}")
    # FactorSpec construction runs parse/validate/causality; malformed exprs raise.
    return FactorSpec(
        factor_id=str(obj["factor_id"]),
        expression=str(obj["expression"]),
        description=str(obj.get("description", "")),
        economic_hypothesis=str(obj["economic_hypothesis"]),
        expected_sign=int(obj["expected_sign"]),
        generator=generator,
    )


def generate_ai(context: str, provider: LLMProvider | None = None) -> FactorSpec:
    provider = provider or MockProvider()
    prompt = PROMPT_TEMPLATE.format(context=context)
    raw = provider.complete(prompt)
    return parse_ai_factor(raw, generator="ai", llm_model=provider.model)


# JSON schema the model is asked to conform to (structured outputs).
_FACTOR_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "factor_id": {"type": "string"},
        "expression": {"type": "string"},
        "description": {"type": "string"},
        "economic_hypothesis": {"type": "string"},
        "expected_sign": {"type": "integer", "enum": [-1, 0, 1]},
        "required_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["factor_id", "expression", "economic_hypothesis", "expected_sign", "required_fields"],
    "additionalProperties": False,
}


class AnthropicProvider:
    """Optional real LLM provider backed by the Anthropic API.

    This is the only part of Emberforge that can reach the network, and it is
    strictly opt-in: the package's core, tests, and demo never construct it.
    Requires ``pip install 'emberforge[llm]'`` and Anthropic credentials in the
    environment. The model is asked for structured JSON (never code), and the
    output still runs the full parse -> validate -> causality pipeline via
    :func:`parse_ai_factor`, so the API cannot smuggle in a look-ahead.
    """

    def __init__(self, model: str = "claude-opus-5", max_tokens: int = 1024, client=None):
        self.model = model
        self.max_tokens = max_tokens
        self._client = client

    def _get_client(self):
        if self._client is None:
            import anthropic  # imported lazily so the core has no hard dependency

            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, prompt: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=(
                "You are a quantitative researcher proposing ONE cross-sectional "
                "equity factor. Respond only with JSON matching the provided schema. "
                "The expression must use the Emberforge factor DSL, never Python code."
            ),
            output_config={"format": {"type": "json_schema", "schema": _FACTOR_JSON_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            raise AISchemaError("the model refused the factor-generation request")
        return next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
