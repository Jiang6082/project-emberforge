"""End-to-end research pipeline for a search family.

Runs the full workflow: compute -> evaluate -> record every experiment ->
family-level multiple-testing (BH/Holm) -> Deflated Sharpe (using the family
trial count) -> PBO across the family -> deduplication -> decision. Failed and
duplicate candidates are recorded, never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..analytics import FactorEvaluation, evaluate_factor
from ..compute import PreprocessConfig, compute_factor
from ..data.schema import MarketData
from ..dedup import novelty_report
from ..dsl.spec import FactorSpec
from ..registry import ExperimentRecord, ExperimentRegistry
from ..stats import (
    benjamini_hochberg,
    circular_block_bootstrap,
    cpcv_path_distribution,
    deflated_sharpe,
    hansens_spa,
    holm,
    ic_pvalue,
    pbo_cpcv,
    pbo_cscv,
    whites_reality_check,
)
from .decision import DecisionState, PromotionCriteria, decide


@dataclass
class CandidateResult:
    spec: FactorSpec
    evaluation: FactorEvaluation
    scores: pd.DataFrame = field(repr=False)
    report: dict = field(default_factory=dict)
    experiment_id: str = ""


@dataclass
class FamilyStudy:
    family: str
    results: list[CandidateResult]
    pbo: float
    survivors: list[str]

    def report_rows(self) -> list[dict]:
        return [r.report for r in self.results]


def run_family_study(
    family: str,
    specs: list[FactorSpec],
    data: MarketData,
    registry: ExperimentRegistry,
    *,
    horizon: int = 1,
    preprocess: PreprocessConfig = PreprocessConfig(),
    criteria: PromotionCriteria = PromotionCriteria(),
    seed: int = 0,
    universe=None,
) -> FamilyStudy:
    from ..report import candidate_report_dict  # local import avoids report<->research cycle

    eligibility = universe.eligibility(data.index, data.symbols) if universe is not None else None
    universe_fp = universe.fingerprint if universe is not None else data.metadata.fingerprint

    # 1) compute + evaluate + record every experiment (including future failures)
    results: list[CandidateResult] = []
    for spec in specs:
        try:
            scores = compute_factor(spec, data, preprocess, eligibility=eligibility)
            evaluation = evaluate_factor(spec, data, horizon=horizon, preprocess=preprocess, universe=universe)
            status = "evaluated"
            failure = None
        except Exception as exc:  # invalid / degenerate factor still gets recorded
            rec = ExperimentRecord(
                factor_id=spec.factor_id, family=family, expression=spec.expression,
                expression_hash=spec.expression_hash, status="invalid",
                generator=spec.generator, failure_reason=str(exc), seed=seed,
                dataset_fingerprint=data.metadata.fingerprint,
            )
            registry.record(rec)
            continue
        rec = ExperimentRecord(
            factor_id=spec.factor_id, family=family, expression=spec.expression,
            expression_hash=spec.expression_hash, status=status, generator=spec.generator,
            parent_id=(spec.parent_ids[0] if spec.parent_ids else None),
            failure_reason=failure, seed=seed,
            dataset_fingerprint=data.metadata.fingerprint,
            universe_fingerprint=universe_fp,
            metrics=evaluation.to_metrics(),
        )
        exp_id = registry.record(rec)
        results.append(CandidateResult(spec, evaluation, scores, experiment_id=exp_id))

    if not results:
        return FamilyStudy(family, [], float("nan"), [])

    n_trials = registry.family_trial_count(family)

    # 2) family-level multiple testing on IC t-stat p-values
    pvals = [ic_pvalue(r.evaluation.ic.t_stat, r.evaluation.ic.n) for r in results]
    pvals = [p if p == p else 1.0 for p in pvals]  # NaN -> 1.0
    bh = benjamini_hochberg(pvals)
    hl = holm(pvals)

    # 3) PBO across the family from aligned LS return series
    ls_frame = pd.DataFrame({r.spec.factor_id: r.evaluation.ls_returns for r in results}).dropna()
    have_family = ls_frame.shape[1] >= 2 and len(ls_frame) >= 8
    pbo = pbo_cscv(ls_frame.values, n_splits=8).pbo if have_family else float("nan")
    pbo_cpcv_val = (
        pbo_cpcv(ls_frame.values, n_groups=6, n_test_groups=2).pbo
        if ls_frame.shape[1] >= 2 and len(ls_frame) >= 12 else float("nan")
    )
    # family-wide data-snooping tests over the best-of-N (White RC, Hansen SPA)
    if ls_frame.shape[1] >= 2 and len(ls_frame) >= 20:
        white_rc_p = whites_reality_check(ls_frame.values, n_boot=500, seed=seed).p_value
        spa_p = hansens_spa(ls_frame.values, n_boot=500, seed=seed).p_value
    else:
        white_rc_p = spa_p = float("nan")

    # variance of per-period Sharpe across the family, for the DSR trial penalty
    per_period_sr = []
    for r in results:
        rr = r.evaluation.ls_returns.dropna()
        if len(rr) > 2 and rr.std(ddof=1) > 0:
            per_period_sr.append(rr.mean() / rr.std(ddof=1))
    sr_var = float(np.var(per_period_sr, ddof=1)) if len(per_period_sr) > 1 else None

    # 4) per-candidate: DSR, bootstrap CI, dedup, decision
    survivors: list[str] = []
    for i, r in enumerate(results):
        dsr = deflated_sharpe(r.evaluation.ls_returns, n_trials=n_trials, sr_variance=sr_var)
        ci = circular_block_bootstrap(r.evaluation.ls_returns, statistic="sharpe", seed=seed)
        cpath = cpcv_path_distribution(r.evaluation.ls_returns, n_groups=6, n_test_groups=2)
        # keep-first dedup: only compare against *earlier* candidates, so the
        # first occurrence survives and later copies are flagged as duplicates.
        prior = results[:i]
        prior_scores = {x.spec.factor_id: x.scores for x in prior}
        prior_specs = [x.spec for x in prior]
        nov = novelty_report(r.spec, r.scores, prior_specs, prior_scores,
                             corr_threshold=criteria.max_correlation)
        stats = {
            "p_raw": pvals[i],
            "p_fdr": bh[i].p_adjusted,
            "fdr_reject": bh[i].reject,
            "p_holm": hl[i].p_adjusted,
            "dsr": dsr.dsr,
            "pbo": pbo,
            "pbo_cpcv": pbo_cpcv_val,   # family-level (combinatorial paths)
            "white_rc_p": white_rc_p,   # family-level (same across the family)
            "spa_p": spa_p,             # family-level
            "sharpe_ci_lo": ci.lower,
            "sharpe_ci_hi": ci.upper,
            "cpcv_oos_sharpe_median": cpath.median,   # per-candidate path robustness
            "cpcv_oos_sharpe_p05": cpath.p05,
            "cpcv_oos_frac_positive": cpath.fraction_positive,
        }
        nearest = nov.nearest.correlation if nov.nearest else None
        decision = decide(
            r.spec.factor_id, r.evaluation.to_metrics(),
            is_duplicate=nov.is_duplicate, fdr_reject=bh[i].reject,
            dsr=dsr.dsr, nearest_corr=nearest, criteria=criteria,
        )
        registry.update_status(r.experiment_id, decision.state.value,
                               failure_reason="; ".join(decision.reasons) if "reject" in decision.state.value else None)
        r.report = candidate_report_dict(
            r.spec, r.evaluation, nov, decision, stats,
            trial_count=n_trials, holdout_views=registry.holdout_access_count(family),
        )
        if decision.state == DecisionState.RESEARCH_SURVIVOR:
            survivors.append(r.spec.factor_id)

    return FamilyStudy(family, results, pbo, survivors)


__all__ = ["run_family_study", "FamilyStudy", "CandidateResult"]
