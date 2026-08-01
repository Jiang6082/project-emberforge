"""Offline, versioned, checksummed candidate bundle.

This is the ONLY channel to Project Geld: a manual, one-way, offline directory
that Geld can later validate by hand. There are no API calls, shared databases,
or hooks. Exporting requires an explicit human-approved decision state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..dsl.spec import FactorSpec
from ..registry.gitinfo import git_provenance

BUNDLE_SCHEMA_VERSION = "1.0.0"


class ApprovalError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def export_candidate(
    spec: FactorSpec,
    out_dir: str | Path,
    *,
    evaluation_metrics: dict,
    statistics: dict,
    lineage: list[dict],
    novelty: dict,
    data_provenance: dict,
    report_md: str,
    approved: bool,
    trial_count: int,
    holdout_views: int,
    limitations: list[str] | None = None,
    repo_root: str | Path | None = None,
) -> Path:
    """Write a candidate bundle. Raises unless ``approved`` is True."""
    if not approved:
        raise ApprovalError(
            "export requires an explicit human-approved decision state; refusing to export"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    prov = git_provenance(repo_root)
    factor = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "candidate_id": spec.factor_id,
        "expression": spec.expression,           # immutable, declarative
        "canonical_expression": spec.canonical_expression,
        "expression_hash": spec.expression_hash,
        "required_fields": list(spec.required_fields),
        "intended_frequency": spec.intended_frequency,
        "max_lookback": spec.max_lookback,
        "expected_sign": spec.expected_sign,
        "complexity_score": spec.complexity_score,
    }
    evaluation = {
        "metrics": evaluation_metrics,
        "statistics": statistics,
        "trial_count": trial_count,
        "holdout_views": holdout_views,
    }
    # write component files (report + json parts)
    _write(out / "factor.json", json.dumps(factor, indent=2, sort_keys=True))
    _write(out / "hypothesis.md", f"# {spec.factor_id}\n\n{spec.economic_hypothesis}\n")
    _write(out / "evaluation.json", json.dumps(evaluation, indent=2, sort_keys=True))
    _write(out / "lineage.json", json.dumps(lineage, indent=2, sort_keys=True, default=str))
    _write(out / "data_provenance.json", json.dumps(data_provenance, indent=2, sort_keys=True))
    _write(out / "report.md", report_md)

    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "candidate_id": spec.factor_id,
        "expression_hash": spec.expression_hash,
        "source_project": "emberforge",
        "source_commit": prov["git_commit"],
        "source_dirty": prov["git_dirty"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approval_state": "human_approved",
        "universe_assumptions": data_provenance.get("universe", "research-only"),
        "preprocessing": evaluation_metrics.get("preprocessing", "see evaluation.json"),
        "known_limitations": limitations or [
            "Research artifact; not validated for live trading.",
            "Statistics are trial-count- and holdout-history-dependent.",
        ],
        "nearest_duplicates": novelty.get("nearest_duplicates", []),
        "files": [],  # filled below
    }
    _write(out / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

    # checksums over every file except checksums.txt itself
    checksum_lines = []
    files = sorted(p for p in out.iterdir() if p.name != "checksums.txt")
    for p in files:
        digest = _sha256(p.read_bytes())
        checksum_lines.append(f"{digest}  {p.name}")
    manifest["files"] = [p.name for p in files]
    _write(out / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    # recompute manifest checksum after adding file list
    checksum_lines = []
    for p in sorted(x for x in out.iterdir() if x.name != "checksums.txt"):
        checksum_lines.append(f"{_sha256(p.read_bytes())}  {p.name}")
    _write(out / "checksums.txt", "\n".join(checksum_lines) + "\n")
    return out


def verify_bundle(bundle_dir: str | Path) -> tuple[bool, list[str]]:
    """Recompute checksums and confirm bundle integrity."""
    out = Path(bundle_dir)
    checks = (out / "checksums.txt").read_text().strip().splitlines()
    problems = []
    recorded = {}
    for line in checks:
        digest, name = line.split("  ", 1)
        recorded[name] = digest
    for p in out.iterdir():
        if p.name == "checksums.txt":
            continue
        actual = _sha256(p.read_bytes())
        if recorded.get(p.name) != actual:
            problems.append(f"checksum mismatch: {p.name}")
    missing = set(recorded) - {p.name for p in out.iterdir()}
    problems += [f"missing file: {m}" for m in missing]
    return (not problems), problems
