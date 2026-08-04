"""The automated pipeline: generate → evaluate → auto-export → report, no human gate."""

import json

import pytest

from emberforge.export import validate_bundle
from emberforge.pipeline import run_pipeline

pytestmark = pytest.mark.slow


def test_pipeline_auto_exports_survivors_and_writes_html(tmp_path):
    out = tmp_path / "run"
    summary = run_pipeline(out_dir=out, families=["momentum", "reversal", "volatility"], seed=7)

    # it recorded everything (including failures) and found at least one survivor
    assert summary["n_candidates"] >= 6
    assert summary["survivors"], "expected at least one auto-promoted survivor"

    # a nice HTML report is written every run
    html = (out / "report.html").read_text()
    assert html.startswith("<!doctype html>") and "grp-adj" in html
    assert (out / "family_report.md").exists()

    # every survivor was exported automatically as a valid bundle
    assert summary["exported"]
    for e in summary["exported"]:
        assert e["valid"] is True
        manifest = json.loads((out / "bundles" / e["factor_id"] / "manifest.json").read_text())
        assert manifest["approval_state"] == "auto_approved"


def test_pipeline_no_approve_writes_reports_without_export(tmp_path):
    out = tmp_path / "run"
    summary = run_pipeline(out_dir=out, families=["momentum"], seed=7, auto_approve=False)
    assert (out / "report.html").exists()
    assert summary["exported"] == []
    assert not (out / "bundles").exists()


def test_pipeline_exported_bundle_independently_validates(tmp_path):
    out = tmp_path / "run"
    summary = run_pipeline(out_dir=out, families=["momentum"], seed=7)
    for e in summary["exported"]:
        assert validate_bundle(e["dir"]).ok
