"""Adapter: Emberforge candidate → Project Geld's ``candidate_bundle_v1`` JSON.

Emberforge and Geld independently grew *different* bundle schemas. Geld's importer
(`geld/candidates/`) expects a single JSON object with fields like ``signal_spec``,
``required_inputs``, ``frequency``, ``approval_status``. This module maps an
Emberforge candidate onto that contract so the offline hand-off actually works.

Emberforge never imports Geld — the constants below *mirror* Geld's contract (kept
in sync by hand) so the two stay decoupled. The output is data-only JSON (no code),
which Geld validates before quarantining; importing never enables trading.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__

# --- mirror of Geld's candidate_bundle_v1 contract (geld/candidates/validator.py) ---
GELD_SCHEMA_VERSION = "candidate_bundle_v1"
GELD_ALLOWED_INPUTS = {"open", "high", "low", "close", "volume", "vwap"}
GELD_ALLOWED_FREQ = {"1Min", "5Min", "15Min", "1Day"}
GELD_ALLOWED_APPROVAL = {"draft", "approved", "rejected"}

_FREQ_MAP = {"daily": "1Day", "1Min": "1Min", "5Min": "5Min", "15Min": "15Min"}
# Emberforge's synthesized 'returns' field derives from close; map it back.
_INPUT_MAP = {"returns": "close"}
_APPROVAL_MAP = {"human_approved": "approved", "auto_approved": "approved"}


def _required_inputs(fields) -> list[str]:
    out = []
    for f in fields:
        mapped = _INPUT_MAP.get(f, f)
        if mapped in GELD_ALLOWED_INPUTS and mapped not in out:
            out.append(mapped)
    return out or ["close"]


def to_geld_bundle_v1(
    *,
    factor: dict,
    metrics: dict,
    statistics: dict,
    hypothesis: str,
    data_provenance: dict,
    approval_state: str = "auto_approved",
    name: str | None = None,
    source_commit: str | None = None,
) -> dict:
    """Build a ``candidate_bundle_v1`` dict from Emberforge's factor + evidence.

    ``factor`` is Emberforge's ``factor.json`` payload; ``metrics`` / ``statistics``
    come from the evaluation. Returns a plain dict ready to write as JSON.
    """
    freq = _FREQ_MAP.get(factor.get("intended_frequency", "daily"), "1Day")
    pb = metrics.get("portfolio_backtest") or {}
    bundle = {
        "bundle_schema_version": GELD_SCHEMA_VERSION,
        "candidate_id": factor["candidate_id"],
        "name": name or factor["candidate_id"],
        "source_project_version": f"emberforge {__version__}" + (f"+{source_commit[:12]}" if source_commit else ""),
        "signal_spec": {
            "kind": "expression",
            "expression": factor.get("canonical_expression") or factor["expression"],
            "parameters": {"expected_sign": factor.get("expected_sign", 0)},
        },
        "economic_hypothesis": (hypothesis or "").strip() or "(no hypothesis provided)",
        "required_inputs": _required_inputs(factor.get("required_fields", ["close"])),
        "frequency": freq,
        "lookback": max(1, int(factor.get("max_lookback", 1) or 1)),
        "approval_status": _APPROVAL_MAP.get(approval_state, "draft"),
        "created_at": datetime.now(UTC).isoformat(),
        "universe_assumptions": data_provenance.get("universe", "research-only"),
        "preprocessing": {"winsorize": True, "cross_sectional_zscore": True},
        "portfolio_construction": metrics.get("portfolio_spec") or {},
        "evaluation_summary": {
            "mean_ic": metrics.get("mean_ic"),
            "ic_t_stat": metrics.get("ic_t_stat"),
            "diagnostic_sharpe": metrics.get("sharpe"),
            "portfolio_backtest_sharpe": pb.get("sharpe"),
            "max_drawdown": pb.get("max_drawdown"),
            "total_return": pb.get("total_return"),
            "turnover": metrics.get("turnover"),
            "capacity_usd": metrics.get("capacity_usd"),
            "deflated_sharpe": statistics.get("dsr"),
            "survives_fdr": statistics.get("fdr_reject"),
            "bh_p_value": statistics.get("p_fdr"),
            "pbo_cscv": statistics.get("pbo"),
            "pbo_cpcv": statistics.get("pbo_cpcv"),
            "white_reality_check_p": statistics.get("white_rc_p"),
            "spa_p": statistics.get("spa_p"),
            "trial_count": statistics.get("trial_count") or metrics.get("trial_count"),
            "emberforge_approval_state": approval_state,
        },
        "data_fingerprint": data_provenance.get("dataset_fingerprint", ""),
        "code_hash": factor.get("expression_hash", ""),
    }
    return bundle


def from_native_bundle(bundle_dir: str | Path, approval_state: str = "auto_approved") -> dict:
    """Convert an already-exported Emberforge native bundle folder to v1 JSON."""
    d = Path(bundle_dir)
    factor = json.loads((d / "factor.json").read_text())
    evaluation = json.loads((d / "evaluation.json").read_text())
    manifest = json.loads((d / "manifest.json").read_text())
    hypothesis = (d / "hypothesis.md").read_text() if (d / "hypothesis.md").exists() else ""
    # strip the leading "# title" line from hypothesis.md
    hyp = "\n".join(ln for ln in hypothesis.splitlines() if not ln.startswith("#")).strip()
    statistics = {**evaluation.get("statistics", {}), "trial_count": evaluation.get("trial_count")}
    return to_geld_bundle_v1(
        factor=factor,
        metrics=evaluation.get("metrics", {}),
        statistics=statistics,
        hypothesis=hyp,
        data_provenance={
            "universe": manifest.get("universe_assumptions", "research-only"),
            "dataset_fingerprint": manifest.get("expression_hash", ""),
        },
        approval_state=manifest.get("approval_state", approval_state),
        source_commit=manifest.get("source_commit"),
    )


def export_geld_bundle_v1(bundle: dict, path: str | Path) -> Path:
    """Write a v1 bundle dict to a single ``.candidate.json`` file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return p


__all__ = [
    "to_geld_bundle_v1", "from_native_bundle", "export_geld_bundle_v1",
    "GELD_SCHEMA_VERSION", "GELD_ALLOWED_INPUTS", "GELD_ALLOWED_FREQ", "GELD_ALLOWED_APPROVAL",
]
