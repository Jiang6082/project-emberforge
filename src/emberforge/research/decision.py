"""Candidate decision states and promotion logic.

Promotion is deliberately conservative and multi-factor. Crucially, exceeding a
Sharpe threshold is never sufficient — adjusted significance, stability, novelty,
turnover, and trial count all gate promotion. No candidate is ever labelled
"proven alpha".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DecisionState(str, Enum):
    GENERATED = "generated"
    INVALID = "invalid"
    DUPLICATE = "duplicate"
    REJECTED_DEV = "rejected_in_development"
    REJECTED_ROBUSTNESS = "rejected_after_robustness"
    VALIDATION_CANDIDATE = "validation_candidate"
    LOCKED_TEST_EVALUATED = "locked_test_evaluated"
    RESEARCH_SURVIVOR = "research_survivor"
    HUMAN_APPROVED = "human_approved"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"


@dataclass
class PromotionCriteria:
    min_abs_mean_ic: float = 0.01
    min_abs_t_stat: float = 2.0
    max_turnover: float = 0.9
    require_fdr_reject: bool = True
    min_dsr: float = 0.60
    max_correlation: float = 0.7


@dataclass
class DecisionResult:
    factor_id: str
    state: DecisionState
    reasons: list[str] = field(default_factory=list)


def decide(
    factor_id: str,
    metrics: dict,
    *,
    is_duplicate: bool,
    fdr_reject: bool | None,
    dsr: float | None,
    nearest_corr: float | None,
    criteria: PromotionCriteria = PromotionCriteria(),
) -> DecisionResult:
    """Apply the promotion gates in order and return a decision state + reasons."""
    reasons: list[str] = []

    if is_duplicate:
        return DecisionResult(factor_id, DecisionState.DUPLICATE, ["duplicate of an existing factor"])

    t = abs(metrics.get("ic_t_stat") or 0.0)
    mic = abs(metrics.get("mean_ic") or 0.0)
    tvr = metrics.get("turnover")

    if mic < criteria.min_abs_mean_ic:
        reasons.append(f"|mean IC| {mic:.4f} < {criteria.min_abs_mean_ic}")
    if t < criteria.min_abs_t_stat:
        reasons.append(f"|IC t| {t:.2f} < {criteria.min_abs_t_stat}")
    if tvr is not None and tvr == tvr and tvr > criteria.max_turnover:
        reasons.append(f"turnover {tvr:.2f} > {criteria.max_turnover}")
    if reasons:
        return DecisionResult(factor_id, DecisionState.REJECTED_DEV, reasons)

    # robustness / selection-bias gates
    if criteria.require_fdr_reject and fdr_reject is False:
        reasons.append("does not survive Benjamini–Hochberg FDR at the family level")
    if dsr is not None and dsr == dsr and dsr < criteria.min_dsr:
        reasons.append(f"Deflated Sharpe {dsr:.2f} < {criteria.min_dsr} (given trial count)")
    if nearest_corr is not None and nearest_corr == nearest_corr and abs(nearest_corr) > criteria.max_correlation:
        reasons.append(f"correlated {nearest_corr:.2f} with an existing factor")
    if reasons:
        return DecisionResult(factor_id, DecisionState.REJECTED_ROBUSTNESS, reasons)

    return DecisionResult(
        factor_id, DecisionState.RESEARCH_SURVIVOR,
        ["passed development, FDR, deflated-Sharpe and novelty gates (not 'proven alpha')"],
    )


__all__ = ["DecisionState", "PromotionCriteria", "DecisionResult", "decide"]
