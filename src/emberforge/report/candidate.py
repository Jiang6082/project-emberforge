"""Standardized candidate reports (Markdown + machine-readable dict)."""

from __future__ import annotations

import json
from dataclasses import asdict

from ..analytics import FactorEvaluation
from ..dedup import NoveltyReport
from ..dsl.spec import FactorSpec
from ..research.decision import DecisionResult


def _fmt(x, nd=4):
    try:
        if x is None or x != x:
            return "n/a"
        return f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def candidate_report_dict(
    spec: FactorSpec,
    evaluation: FactorEvaluation,
    novelty: NoveltyReport,
    decision: DecisionResult,
    stats: dict,
    trial_count: int,
    holdout_views: int,
) -> dict:
    return {
        "factor_id": spec.factor_id,
        "expression": spec.expression,
        "canonical_expression": spec.canonical_expression,
        "expression_hash": spec.expression_hash,
        "family": novelty.family,
        "economic_hypothesis": spec.economic_hypothesis,
        "expected_sign": spec.expected_sign,
        "required_fields": list(spec.required_fields),
        "max_lookback": spec.max_lookback,
        "complexity_score": spec.complexity_score,
        "parent_ids": list(spec.parent_ids),
        "trial_count": trial_count,
        "holdout_views": holdout_views,
        "metrics": evaluation.to_metrics(),
        "statistics": stats,
        "nearest_duplicates": [
            {"factor_id": m.factor_id, "correlation": m.correlation} for m in novelty.correlated
        ],
        "syntactic_duplicates": novelty.syntactic_duplicates,
        "decision": decision.state.value,
        "decision_reasons": decision.reasons,
        "reproduce": f"emberforge factor evaluate '{spec.expression}'",
    }


def candidate_report_md(report: dict) -> str:
    m = report["metrics"]
    s = report["statistics"]
    lines = [
        f"# Candidate report — `{report['factor_id']}`",
        "",
        f"**Decision:** `{report['decision']}`  ·  **Family:** {report['family']}  ·  "
        f"**Trials in family:** {report['trial_count']}  ·  **Holdout views:** {report['holdout_views']}",
        "",
        "> Diagnostic metrics only. This is **not** proven alpha and the diagnostic "
        "long-short portfolio is not an executable strategy.",
        "",
        "## Hypothesis",
        report["economic_hypothesis"] or "_none provided_",
        "",
        "## Factor definition",
        f"- Expression: `{report['expression']}`",
        f"- Canonical: `{report['canonical_expression']}`",
        f"- Hash: `{report['expression_hash']}`",
        f"- Expected sign: {report['expected_sign']}  ·  Max lookback: {report['max_lookback']}  ·  "
        f"Complexity: {report['complexity_score']}",
        f"- Required fields: {', '.join(report['required_fields'])}",
        f"- Lineage / parents: {', '.join(report['parent_ids']) or 'root'}",
        "",
        "## Raw diagnostics",
        f"| metric | value |",
        f"|---|---|",
        f"| periods | {m['n_periods']} |",
        f"| mean IC | {_fmt(m['mean_ic'])} |",
        f"| IC IR | {_fmt(m['ic_ir'])} |",
        f"| IC t-stat | {_fmt(m['ic_t_stat'], 2)} |",
        f"| IC hit rate | {_fmt(m['ic_hit_rate'], 2)} |",
        f"| LS Sharpe | {_fmt(m['sharpe'], 2)} |",
        f"| LS Sharpe (after cost) | {_fmt(m['sharpe_after_cost'], 2)} |",
        f"| turnover | {_fmt(m['turnover'], 2)} |",
        f"| quantile monotonicity | {_fmt(m['monotonicity'], 2)} |",
        f"| coverage | {_fmt(m['coverage'], 2)} |",
        f"| score autocorr | {_fmt(m['autocorr'], 2)} |",
        "",
        f"IC decay by horizon: " + ", ".join(f"h{h}={_fmt(v,3)}" for h, v in m["ic_decay"].items()),
        "",
        "## Adjusted evidence (selection-bias aware)",
        f"| statistic | value |",
        f"|---|---|",
        f"| raw IC p-value | {_fmt(s.get('p_raw'), 4)} |",
        f"| BH-adjusted p-value | {_fmt(s.get('p_fdr'), 4)} |",
        f"| survives FDR | {s.get('fdr_reject')} |",
        f"| Holm-adjusted p-value | {_fmt(s.get('p_holm'), 4)} |",
        f"| Deflated Sharpe | {_fmt(s.get('dsr'), 3)} |",
        f"| PBO (family) | {_fmt(s.get('pbo'), 3)} |",
        f"| Sharpe 95% block-bootstrap CI | [{_fmt(s.get('sharpe_ci_lo'),2)}, {_fmt(s.get('sharpe_ci_hi'),2)}] |",
        "",
        "## Novelty",
    ]
    if report["syntactic_duplicates"]:
        lines.append(f"- Syntactic duplicates: {', '.join(report['syntactic_duplicates'])}")
    if report["nearest_duplicates"]:
        for d in report["nearest_duplicates"][:5]:
            lines.append(f"- Correlated with `{d['factor_id']}`: {_fmt(d['correlation'],2)}")
    if not report["syntactic_duplicates"] and not report["nearest_duplicates"]:
        lines.append("- No duplicates above threshold.")
    lines += [
        "",
        "## Decision rationale",
        *[f"- {r}" for r in report["decision_reasons"]],
        "",
        "## Limitations",
        "- Synthetic/small data; assumptions (iid IC periods for the t-stat) are approximate.",
        "- Diagnostic portfolio ignores real fills, borrow, and capacity.",
        "- Statistical adjustments depend on the recorded trial count; see the registry.",
        "",
        "## Reproduce",
        "```bash",
        report["reproduce"],
        "```",
    ]
    return "\n".join(lines)
