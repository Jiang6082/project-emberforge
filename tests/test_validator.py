"""The standalone bundle validator independently re-checks an exported bundle."""

import json

from emberforge.dsl import make_factor
from emberforge.export import export_candidate, validate_bundle


def _export(tmp_path, expression="ts_returns(close, 20)"):
    spec = make_factor("m", expression, economic_hypothesis="momentum")
    return export_candidate(
        spec, tmp_path / "bundle",
        evaluation_metrics={"mean_ic": 0.03},
        statistics={"dsr": 0.7, "fdr_reject": True},
        lineage=[{"factor_id": "m"}],
        novelty={"nearest_duplicates": []},
        data_provenance={"dataset_fingerprint": "abc", "universe": ["A", "B"]},
        report_md="# report",
        approved=True,
        trial_count=12,
        holdout_views=0,
    )


def test_valid_bundle_passes(tmp_path):
    out = _export(tmp_path)
    result = validate_bundle(out)
    assert result.ok, result.problems
    assert all(result.checks.values())
    assert result.checks["expression_causal"]
    assert result.checks["hash_matches"]


def test_tampered_expression_fails_hash_and_causality(tmp_path):
    out = _export(tmp_path)
    factor = json.loads((out / "factor.json").read_text())
    factor["expression"] = "ts_returns(close, 5)"  # changed, hash now stale
    (out / "factor.json").write_text(json.dumps(factor))
    result = validate_bundle(out)
    assert not result.ok
    # checksum will also break, but the independent hash recompute is the point
    assert result.checks.get("hash_matches") is False


def test_lookahead_expression_rejected(tmp_path):
    # bypass export validation by writing a leaky expression straight into the bundle
    out = _export(tmp_path)
    factor = json.loads((out / "factor.json").read_text())
    factor["expression"] = "ts_delay(close, -1)"
    (out / "factor.json").write_text(json.dumps(factor))
    result = validate_bundle(out)
    assert result.checks.get("expression_causal") is False


def test_unapproved_manifest_fails(tmp_path):
    out = _export(tmp_path)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["approval_state"] = "draft"
    (out / "manifest.json").write_text(json.dumps(manifest))
    result = validate_bundle(out)
    assert result.checks.get("human_approved") is False


def test_unsupported_schema_version_fails(tmp_path):
    out = _export(tmp_path)
    factor = json.loads((out / "factor.json").read_text())
    factor["schema_version"] = "9.9.9"
    (out / "factor.json").write_text(json.dumps(factor))
    result = validate_bundle(out)
    assert result.checks.get("schema_supported") is False


def test_missing_files_fails_cleanly(tmp_path):
    out = _export(tmp_path)
    (out / "factor.json").unlink()
    result = validate_bundle(out)
    assert not result.ok
    assert result.checks.get("files_present") is False
