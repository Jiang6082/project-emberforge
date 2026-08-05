"""Contract hardening for the offline Emberforge → Geld ``candidate_bundle_v1``.

Three guarantees the hand-off depends on:

* **Determinism** — converting the same native bundle twice yields byte-identical
  v1 JSON, so its checksum is reproducible across machines and runs.
* **Schema stability** — the exact field surface of ``candidate_bundle_v1`` is
  frozen here; any add/remove/rename fails this test, forcing a *conscious*
  decision to keep the Geld side in sync (the schema is mirrored by hand).
* **Provenance carry-through** — the dataset fingerprint, factor/code hash, and
  trial count survive the native → v1 conversion, so a Geld paper run traces back
  to the exact Emberforge experiment and dataset.
"""

from __future__ import annotations

import json

from emberforge.dsl import make_factor
from emberforge.export import export_candidate, from_native_bundle, to_geld_bundle_v1
from emberforge.export.geld_bundle import GELD_SCHEMA_VERSION

# The frozen v1 contract surface. Update these ONLY together with Geld's
# geld/candidates/validator.py — that is the whole point of freezing them.
EXPECTED_TOP_KEYS = {
    "bundle_schema_version", "candidate_id", "name", "source_project_version",
    "signal_spec", "economic_hypothesis", "required_inputs", "frequency",
    "lookback", "approval_status", "created_at", "universe_assumptions",
    "preprocessing", "portfolio_construction", "evaluation_summary",
    "data_fingerprint", "code_hash",
}
EXPECTED_SIGNAL_KEYS = {"kind", "expression", "parameters"}
EXPECTED_EVAL_KEYS = {
    "mean_ic", "ic_t_stat", "diagnostic_sharpe", "portfolio_backtest_sharpe",
    "max_drawdown", "total_return", "turnover", "capacity_usd", "deflated_sharpe",
    "survives_fdr", "bh_p_value", "pbo_cscv", "pbo_cpcv", "white_reality_check_p",
    "spa_p", "trial_count", "emberforge_approval_state",
}


def _native(tmp_path):
    spec = make_factor(
        "mom20", "ts_returns(close, 20)",
        economic_hypothesis="20-bar momentum persists.", expected_sign=1,
    )
    return export_candidate(
        spec, tmp_path / "native",
        evaluation_metrics={"mean_ic": 0.07, "ic_t_stat": 4.7, "sharpe": 2.5, "turnover": 0.17},
        statistics={"dsr": 0.71, "fdr_reject": True, "p_fdr": 0.0001, "pbo": 0.2},
        lineage=[{"factor_id": "mom20"}], novelty={"nearest_duplicates": []},
        data_provenance={"dataset_fingerprint": "DATASET-abc123", "universe": ["A", "B"],
                         "source": "synthetic", "frequency": "daily", "feed": "sim"},
        report_md="# r", approved=True, trial_count=17, holdout_views=0,
        approval_state="auto_approved",
    )


def test_from_native_bundle_is_deterministic(tmp_path):
    native = _native(tmp_path)
    a = from_native_bundle(native)
    b = from_native_bundle(native)
    # Byte-identical JSON — the conversion is a pure function of the bundle on disk
    # (no wall-clock 'created_at' leaking in), so its checksum is reproducible.
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    # created_at traces back to the native bundle, not the moment of conversion.
    manifest = json.loads((native / "manifest.json").read_text(encoding="utf-8"))
    assert a["created_at"] == manifest["created_at"]


def test_v1_schema_surface_is_frozen(tmp_path):
    b = from_native_bundle(_native(tmp_path))
    assert b["bundle_schema_version"] == GELD_SCHEMA_VERSION == "candidate_bundle_v1"
    assert set(b) == EXPECTED_TOP_KEYS, "candidate_bundle_v1 top-level fields changed — sync Geld"
    assert set(b["signal_spec"]) == EXPECTED_SIGNAL_KEYS, "signal_spec fields changed — sync Geld"
    assert set(b["evaluation_summary"]) == EXPECTED_EVAL_KEYS, "evaluation_summary fields changed — sync Geld"


def test_dataset_fingerprint_is_distinct_from_code_hash(tmp_path):
    native = _native(tmp_path)
    factor = json.loads((native / "factor.json").read_text(encoding="utf-8"))
    b = from_native_bundle(native)
    # data_fingerprint must be the DATASET fingerprint (what data the factor was
    # measured on), not a copy of the factor's expression/code hash. This is the
    # traceability contract: Geld can tie a paper run to the exact dataset.
    assert b["data_fingerprint"] == "DATASET-abc123"
    assert b["code_hash"] == factor["expression_hash"]
    assert b["data_fingerprint"] != b["code_hash"]


def test_trial_count_carries_through(tmp_path):
    b = from_native_bundle(_native(tmp_path))
    assert b["evaluation_summary"]["trial_count"] == 17


def test_injected_created_at_is_used():
    b = to_geld_bundle_v1(
        factor={"candidate_id": "x", "expression": "cs_rank(close)",
                "canonical_expression": "cs_rank(close)", "required_fields": ["close"],
                "intended_frequency": "daily", "max_lookback": 1, "expected_sign": 1,
                "expression_hash": "h"},
        metrics={}, statistics={}, hypothesis="h", data_provenance={},
        created_at="2020-01-01T00:00:00+00:00",
    )
    assert b["created_at"] == "2020-01-01T00:00:00+00:00"
