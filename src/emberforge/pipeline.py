"""Automated research pipeline — generate, evaluate, and auto-export survivors.

This is the "run it and read the report" entry point. It skips the human sign-off
step: any candidate that clears the multi-gate decision function is promoted and
exported automatically (with ``approval_state="auto_approved"`` in the manifest,
so provenance stays honest). Every run writes a nice HTML dashboard plus Markdown
reports for a human to read, and a machine-readable summary.

Nothing here trades or touches Project Geld — it only produces vetted factor
bundles. Turning a bundle into live signals still happens on the Geld side.
"""

from __future__ import annotations

import json
from pathlib import Path

from .analytics import evaluate_factor  # noqa: F401  (kept for parity / downstream use)
from .data import make_synthetic
from .data.schema import MarketData
from .export import export_candidate, validate_bundle
from .generate import generate_ai, generate_templates
from .generate.templates import TEMPLATES
from .registry import ExperimentRegistry
from .report import candidate_report_md, family_report_html, family_report_md
from .research import run_family_study
from .research.decision import DecisionState


def _ai_specs(context, ai_provider, n_ai):
    out = []
    seen: set[str] = set()
    for i in range(n_ai):
        try:
            s = generate_ai(f"{context} Idea #{i}.", provider=ai_provider)
            if s.expression_hash not in seen:
                seen.add(s.expression_hash)
                out.append(s)
        except Exception:
            continue
    return out


def run_pipeline(
    out_dir: str | Path,
    data: MarketData | None = None,
    families: list[str] | None = None,
    family_name: str = "pipeline",
    seed: int = 7,
    horizons: tuple[int, ...] = (5, 10, 20, 60),
    ai_provider=None,
    n_ai: int = 0,
    auto_approve: bool = True,
    registry_path: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> dict:
    """Run the whole loop and auto-export every survivor. Returns a summary dict."""
    out = Path(out_dir)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    data = data if data is not None else make_synthetic(seed=seed)
    families = [f for f in (families or list(TEMPLATES)) if f in TEMPLATES]
    registry = ExperimentRegistry(registry_path or out / "registry.sqlite3", repo_root=repo_root)

    # One study per *search family* — multiple-testing is scoped per family, so a
    # factor is judged against its own kind (momentum vs. reversal are distinct).
    results = []
    survivors = []
    for fam in families:
        fam_specs = list(generate_templates(which=[fam], horizons=horizons))
        study = run_family_study(fam, fam_specs, data, registry, seed=seed)
        results.extend(study.results)
        survivors.extend(study.survivors)
    if ai_provider is not None and n_ai > 0:
        ai_specs = _ai_specs(f"Propose a factor in one of: {families}.", ai_provider, n_ai)
        if ai_specs:
            study = run_family_study("ai", ai_specs, data, registry, seed=seed)
            results.extend(study.results)
            survivors.extend(study.survivors)

    # per-candidate reports (human + machine)
    for r in results:
        (out / "reports" / f"{r.spec.factor_id}.md").write_text(candidate_report_md(r.report))
        (out / "reports" / f"{r.spec.factor_id}.json").write_text(json.dumps(r.report, indent=2, default=str))

    # aggregate dashboards — Markdown and the nice HTML — across all families
    rows = [r.report for r in results]
    trial_count = len(results)
    (out / "family_report.md").write_text(family_report_md(family_name, rows))
    (out / "report.html").write_text(family_report_html(
        family_name, rows,
        meta={"trial_count": trial_count, "data": f"{len(data.symbols)} symbols × {len(data.index)} bars"},
    ))

    # auto-approve + export every survivor
    exported = []
    if auto_approve:
        bundles = out / "bundles"
        for r in results:
            if r.report.get("decision") != DecisionState.RESEARCH_SURVIVOR.value:
                continue
            bundle_dir = export_candidate(
                r.spec, bundles / r.spec.factor_id,
                evaluation_metrics=r.evaluation.to_metrics(),
                statistics=r.report["statistics"],
                lineage=registry.lineage(r.experiment_id),
                novelty={"nearest_duplicates": r.report["nearest_duplicates"]},
                data_provenance={
                    "dataset_fingerprint": data.metadata.fingerprint,
                    "source": data.metadata.source,
                    "frequency": data.metadata.frequency,
                    "feed": data.metadata.feed,
                    "universe": list(data.symbols),
                },
                report_md=candidate_report_md(r.report),
                approved=True,
                approval_state="auto_approved",
                trial_count=r.report.get("trial_count", trial_count),
                holdout_views=0,  # the pipeline never touches the locked test
                repo_root=repo_root,
            )
            ok = validate_bundle(bundle_dir).ok
            registry.update_status(r.experiment_id, DecisionState.EXPORTED.value)
            exported.append({"factor_id": r.spec.factor_id, "dir": str(bundle_dir), "valid": ok})

    summary = {
        "family": family_name,
        "families": families,
        "n_candidates": len(results),
        "n_recorded": len(registry.list()),
        "survivors": survivors,
        "exported": exported,
        "report_html": str(out / "report.html"),
        "family_report_md": str(out / "family_report.md"),
        "out_dir": str(out),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


__all__ = ["run_pipeline"]
