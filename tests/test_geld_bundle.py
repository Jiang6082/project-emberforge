"""The Emberforge→Geld candidate_bundle_v1 adapter.

The conformance rules below MIRROR geld/candidates/validator.py so Emberforge
stays decoupled (it never imports Geld). A separate, un-committed script
(examples/verify_against_geld.py) cross-checks against Geld's *real* validator.
"""

import json

from emberforge.dsl import make_factor
from emberforge.export import export_candidate, from_native_bundle, to_geld_bundle_v1

# ---- mirror of Geld's candidate_bundle_v1 contract -----------------------------
_REQUIRED = ["bundle_schema_version", "candidate_id", "name", "source_project_version",
             "signal_spec", "economic_hypothesis", "required_inputs", "frequency",
             "lookback", "approval_status", "created_at"]
_ALLOWED_TOP = set(_REQUIRED) | {"universe_assumptions", "preprocessing", "portfolio_construction",
                                 "evaluation_summary", "data_fingerprint", "code_hash"}
_ALLOWED_SIGNAL = {"kind", "expression", "reference", "parameters"}
_ALLOWED_INPUTS = {"open", "high", "low", "close", "volume", "vwap"}
_ALLOWED_FREQ = {"1Min", "5Min", "15Min", "1Day"}
_ALLOWED_APPROVAL = {"draft", "approved", "rejected"}
_FORBIDDEN = {"python", "pickle", "lambda", "exec", "eval", "callable",
              "entrypoint", "shell", "script", "command", "reduce"}


def _tokens(key):
    tok, out = "", []
    for ch in str(key).lower():
        if ch.isalnum():
            tok += ch
        elif tok:
            out.append(tok); tok = ""
    if tok:
        out.append(tok)
    return out


def _leaf_keys(obj):
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(k); keys += _leaf_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys += _leaf_keys(v)
    return keys


def _validate_like_geld(b):
    errors = []
    for k in b:
        if k not in _ALLOWED_TOP:
            errors.append(f"unknown top-level: {k}")
    if isinstance(b.get("signal_spec"), dict):
        for k in b["signal_spec"]:
            if k not in _ALLOWED_SIGNAL:
                errors.append(f"unknown signal_spec key: {k}")
    for leaf in _leaf_keys(b):
        if set(_tokens(leaf)) & _FORBIDDEN:
            errors.append(f"forbidden key token: {leaf}")
    if b.get("bundle_schema_version") != "candidate_bundle_v1":
        errors.append("bad schema version")
    for k in _REQUIRED:
        if k not in b:
            errors.append(f"missing {k}")
    si = b.get("signal_spec", {})
    if si.get("kind") != "expression" or not isinstance(si.get("expression"), str):
        errors.append("bad signal_spec")
    if not (isinstance(b.get("required_inputs"), list) and b["required_inputs"]
            and set(b["required_inputs"]) <= _ALLOWED_INPUTS):
        errors.append("bad required_inputs")
    if b.get("frequency") not in _ALLOWED_FREQ:
        errors.append("bad frequency")
    lb = b.get("lookback")
    if not isinstance(lb, int) or isinstance(lb, bool) or lb < 1:
        errors.append("bad lookback")
    if b.get("approval_status") not in _ALLOWED_APPROVAL:
        errors.append("bad approval_status")
    return errors


def _native(tmp_path, expr="ts_returns(close, 20)", fields=("close",)):
    spec = make_factor("mom20", expr, economic_hypothesis="20-bar momentum persists.", expected_sign=1)
    return export_candidate(
        spec, tmp_path / "native",
        evaluation_metrics={"mean_ic": 0.07, "ic_t_stat": 4.7, "sharpe": 2.5, "turnover": 0.17,
                            "portfolio_spec": {"kind": "cross_sectional_quantile", "quantiles": 5},
                            "portfolio_backtest": {"sharpe": 2.4, "max_drawdown": -0.1, "total_return": 0.5}},
        statistics={"dsr": 0.71, "fdr_reject": True, "p_fdr": 0.0001, "pbo": 0.2},
        lineage=[{"factor_id": "mom20"}], novelty={"nearest_duplicates": []},
        data_provenance={"dataset_fingerprint": "abc", "universe": ["A", "B"]},
        report_md="# r", approved=True, trial_count=12, holdout_views=0,
        approval_state="auto_approved",
    )


def test_adapter_output_conforms_to_geld_contract(tmp_path):
    b = from_native_bundle(_native(tmp_path))
    assert _validate_like_geld(b) == []
    assert b["approval_status"] == "approved"     # auto_approved maps to Geld 'approved'
    assert b["frequency"] == "1Day"               # daily → 1Day
    assert b["signal_spec"]["expression"] == "ts_returns(close,20)"
    assert b["evaluation_summary"]["emberforge_approval_state"] == "auto_approved"


def test_returns_field_maps_to_close():
    spec = make_factor("r", "cs_rank(returns)", economic_hypothesis="h", expected_sign=1)
    b = to_geld_bundle_v1(
        factor={"candidate_id": "r", "expression": "cs_rank(returns)",
                "canonical_expression": "cs_rank(returns)", "required_fields": ["returns"],
                "intended_frequency": "daily", "max_lookback": 1, "expected_sign": 1, "expression_hash": "h"},
        metrics={}, statistics={}, hypothesis="h", data_provenance={},
    )
    assert b["required_inputs"] == ["close"]       # 'returns' is not a Geld input; maps to close
    assert _validate_like_geld(b) == []


def test_bundle_is_json_serializable(tmp_path):
    b = from_native_bundle(_native(tmp_path))
    json.dumps(b)  # must be plain data
