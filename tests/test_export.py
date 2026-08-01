import json

import pytest

from emberforge.dsl import make_factor
from emberforge.export import ApprovalError, export_candidate, verify_bundle


def _export(tmp_path, approved):
    spec = make_factor("m", "ts_returns(close, 20)", economic_hypothesis="momentum")
    return export_candidate(
        spec, tmp_path / "bundle",
        evaluation_metrics={"mean_ic": 0.03},
        statistics={"dsr": 0.7, "fdr_reject": True},
        lineage=[{"factor_id": "m"}],
        novelty={"nearest_duplicates": []},
        data_provenance={"dataset_fingerprint": "abc", "universe": ["A", "B"]},
        report_md="# report",
        approved=approved,
        trial_count=12,
        holdout_views=0,
    )


def test_export_requires_approval(tmp_path):
    with pytest.raises(ApprovalError):
        _export(tmp_path, approved=False)


def test_export_writes_all_bundle_files(tmp_path):
    out = _export(tmp_path, approved=True)
    names = {p.name for p in out.iterdir()}
    assert {"manifest.json", "factor.json", "hypothesis.md", "evaluation.json",
            "lineage.json", "data_provenance.json", "report.md", "checksums.txt"} <= names


def test_bundle_checksums_valid(tmp_path):
    out = _export(tmp_path, approved=True)
    ok, problems = verify_bundle(out)
    assert ok, problems


def test_tampering_breaks_checksum(tmp_path):
    out = _export(tmp_path, approved=True)
    (out / "factor.json").write_text('{"tampered": true}')
    ok, problems = verify_bundle(out)
    assert not ok and problems


def test_factor_json_is_declarative_and_immutable(tmp_path):
    out = _export(tmp_path, approved=True)
    factor = json.loads((out / "factor.json").read_text())
    assert factor["expression"] == "ts_returns(close, 20)"
    assert factor["expression_hash"]
    # no executable python anywhere in the bundle
    assert "expression" in factor and "code" not in factor


def test_manifest_approval_state(tmp_path):
    out = _export(tmp_path, approved=True)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["approval_state"] == "human_approved"
    assert manifest["source_project"] == "emberforge"
