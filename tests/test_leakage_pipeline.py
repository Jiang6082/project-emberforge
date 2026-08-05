"""The research pipeline must enforce *dynamic* leakage detection on every candidate.

Static causality checks (``dsl.causality``) can only inspect the expression tree:
they reject forbidden future operators and non-positive window literals. They are
blind to a look-ahead baked into an operator's *implementation* — an operator with
no window literal to inspect whose ``fn`` nonetheless reaches into the future.

The perturbation detector (``compute.assert_no_lookahead``) is the backstop for
exactly that. These tests register such a leaky operator, then prove the pipeline
records it as invalid and never evaluates or promotes it — and that switching the
dynamic check off is what lets the leak through (so the guard is doing the work).
"""

from __future__ import annotations

import pytest

from emberforge.dsl import make_factor
from emberforge.dsl.operators import REGISTRY, OpSpec
from emberforge.registry import ExperimentRegistry
from emberforge.research import run_family_study

LEAKY_OP = "_ef_test_future"


@pytest.fixture
def leaky_operator():
    """Register an operator that peeks one bar ahead but has NO window literal for
    the static checker to catch, then remove it again."""
    REGISTRY[LEAKY_OP] = OpSpec(
        name=LEAKY_OP, kind="ts", arity=1,
        fn=lambda x: x.shift(-1),   # reads the NEXT bar — pure look-ahead
        window_args=(),             # nothing for static causality to flag
    )
    try:
        yield LEAKY_OP
    finally:
        REGISTRY.pop(LEAKY_OP, None)


def test_leaky_operator_passes_static_but_is_caught_dynamically(leaky_operator, small_data, tmp_path):
    # It really does pass the static gate — otherwise this test proves nothing.
    leaky = make_factor("leaky", f"{LEAKY_OP}(close)")   # no CausalityError here
    causal = make_factor("causal", "ts_returns(close, 10)")

    reg = ExperimentRegistry(tmp_path / "reg.sqlite3")
    study = run_family_study("leak_fam", [leaky, causal], small_data, reg, seed=1)

    # The leaky factor is recorded, marked invalid, and reason names the leak.
    records = {r["factor_id"]: r for r in reg.list(family="leak_fam")}
    assert records["leaky"]["status"] == "invalid"
    assert "look-ahead" in (records["leaky"]["failure_reason"] or "")

    # It is never evaluated and never promoted...
    evaluated_ids = {r.spec.factor_id for r in study.results}
    assert "leaky" not in evaluated_ids
    assert "leaky" not in study.survivors
    # ...while the genuinely causal factor still flows through normally.
    assert "causal" in evaluated_ids


def test_disabling_dynamic_check_lets_the_leak_through(leaky_operator, small_data, tmp_path):
    """Control: with the dynamic check OFF the same leaky factor is evaluated —
    confirming it's the perturbation guard (not some other gate) that catches it."""
    leaky = make_factor("leaky", f"{LEAKY_OP}(close)")
    reg = ExperimentRegistry(tmp_path / "reg.sqlite3")
    study = run_family_study(
        "leak_fam", [leaky], small_data, reg, seed=1, dynamic_leakage_check=False
    )
    records = {r["factor_id"]: r for r in reg.list(family="leak_fam")}
    # Not rejected for leakage; it got evaluated like any other factor.
    assert records["leaky"]["status"] != "invalid"
    assert "leaky" in {r.spec.factor_id for r in study.results}
