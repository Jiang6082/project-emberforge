"""End-to-end demonstration.

Generates a known momentum factor plus duplicates and weak/noise factors, runs
the full study, rejects the weak and duplicate candidates, retains a survivor,
writes reports, and exports one human-approved offline bundle. The point is to
show the *record of everything tried*, not just the winner.
"""

from __future__ import annotations

import json
from pathlib import Path

from .data import make_synthetic
from .dsl import make_factor
from .export import export_candidate, verify_bundle
from .generate import generate_templates
from .registry import ExperimentRegistry
from .report import candidate_report_md, family_report_md
from .research import run_family_study
from .research.decision import DecisionState


def build_candidates():
    """A deliberately mixed bag: real signal, duplicates, and noise."""
    specs = []
    # the true embedded effect: 20-bar momentum
    specs.append(make_factor("momentum_20", "ts_returns(close,20)",
                             economic_hypothesis="20-bar momentum persists.",
                             expected_sign=1, generator="manual"))
    # a syntactic-ish / empirical duplicate of momentum (algebraically similar)
    specs.append(make_factor("momentum_20_dup", "ts_delta(close,20)",
                             economic_hypothesis="Price change over 20 bars (momentum proxy).",
                             expected_sign=1, generator="manual"))
    # weak/noise factors
    specs.append(make_factor("noise_1bar", "ts_returns(close,1)",
                             economic_hypothesis="1-bar return (mostly noise).",
                             expected_sign=1, generator="manual"))
    specs.append(make_factor("vol_25", "neg(ts_std(ts_returns(close,1),25))",
                             economic_hypothesis="Low realized vol premium.",
                             expected_sign=1, generator="manual"))
    # a batch of templates to bulk up the trial count (selection pressure)
    specs.extend(generate_templates(horizons=(3, 5, 10, 60)))
    # de-duplicate by factor_id, keep first occurrence
    seen, unique = set(), []
    for s in specs:
        if s.factor_id not in seen:
            seen.add(s.factor_id)
            unique.append(s)
    return unique


def run_demo(out_dir: str | Path = "runtime/demo") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = make_synthetic(seed=7)
    registry = ExperimentRegistry(out / "registry.sqlite3", repo_root=Path(__file__).resolve().parents[2])

    specs = build_candidates()
    study = run_family_study("momentum_family", specs, data, registry, seed=7)

    # write per-candidate reports
    reports_dir = out / "reports"
    reports_dir.mkdir(exist_ok=True)
    for r in study.results:
        (reports_dir / f"{r.spec.factor_id}.md").write_text(candidate_report_md(r.report), encoding="utf-8")
        (reports_dir / f"{r.spec.factor_id}.json").write_text(json.dumps(r.report, indent=2, default=str), encoding="utf-8")

    # aggregate family report
    (out / "family_report.md").write_text(family_report_md("momentum_family", study.report_rows()), encoding="utf-8")

    # export ONE survivor as a human-approved bundle (human approval simulated here)
    exported = None
    if study.survivors:
        winner = next(r for r in study.results if r.spec.factor_id == study.survivors[0])
        lineage = registry.lineage(winner.experiment_id)
        bundle_dir = export_candidate(
            winner.spec, out / "candidate_bundle",
            evaluation_metrics=winner.evaluation.to_metrics(),
            statistics=winner.report["statistics"],
            lineage=lineage,
            novelty={"nearest_duplicates": winner.report["nearest_duplicates"]},
            data_provenance={
                "dataset_fingerprint": data.metadata.fingerprint,
                "source": data.metadata.source,
                "frequency": data.metadata.frequency,
                "feed": data.metadata.feed,
                "universe": list(data.symbols),
            },
            report_md=candidate_report_md(winner.report),
            approved=True,  # explicit human approval gate
            trial_count=registry.family_trial_count("momentum_family"),
            holdout_views=registry.holdout_access_count("momentum_family"),
            repo_root=Path(__file__).resolve().parents[2],
        )
        ok, problems = verify_bundle(bundle_dir)
        exported = {"dir": str(bundle_dir), "checksums_ok": ok, "problems": problems}

    summary = {
        "n_candidates": len(study.results),
        "n_recorded_experiments": len(registry.list(family="momentum_family")),
        "survivors": study.survivors,
        "rejected": [r.spec.factor_id for r in study.results
                     if r.report.get("decision", "").startswith("rejected")],
        "duplicates": [r.spec.factor_id for r in study.results
                       if r.report.get("decision") == DecisionState.DUPLICATE.value],
        "pbo": study.pbo,
        "exported": exported,
        "out_dir": str(out),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":  # pragma: no cover
    import pprint

    pprint.pprint(run_demo())
