"""Constrained autonomous research agent (Phase B).

The agent composes the existing pieces — generators, the family pipeline, the
registry, budgets, and the decision function — into a bounded loop. It is
deliberately *constrained*: the guardrails are enforced in code, not left to
good intentions.

The agent MAY: inspect prior experiments, pick underexplored families, propose
candidates, screen them on the **development window only**, review the weak ones,
propose a bounded number of mutations, then stop and report.

The agent MAY NOT: run unbounded (a candidate budget caps it); hide failures
(everything is recorded); touch the locked test (it only ever sees a development
subset, and it asserts zero holdout accesses); inflate trial counts; promote on
Sharpe alone (promotion goes through the multi-gate decision function); or reach
Project Geld in any way (it imports nothing from Geld and places no orders).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..analytics.ic import ic_series
from ..compute import compute_factor
from ..data.schema import MarketData
from ..dsl.spec import FactorSpec
from ..generate import generate_ai, generate_templates, mutate_family
from ..generate.templates import TEMPLATES
from ..registry import ExperimentRegistry
from ..registry.holdout import HoldoutGovernor, ResearchBudget, split_by_fraction
from ..research.decision import DecisionState, PromotionCriteria
from ..research.pipeline import FamilyStudy, run_family_study


@dataclass
class AgentRunReport:
    family: str
    families_considered: dict[str, int]      # family -> prior trial count
    n_candidates_evaluated: int
    survivors: list[str]
    rejected: list[str]
    duplicates: list[str]
    budget_candidates: int
    holdout_accesses: int                    # MUST be 0
    stopped_reason: str
    study: FamilyStudy = field(repr=False, default=None)

    def summary(self) -> dict:
        return {
            "family": self.family,
            "families_considered": self.families_considered,
            "n_candidates_evaluated": self.n_candidates_evaluated,
            "survivors": self.survivors,
            "n_rejected": len(self.rejected),
            "n_duplicates": len(self.duplicates),
            "budget_candidates": self.budget_candidates,
            "holdout_accesses": self.holdout_accesses,
            "stopped_reason": self.stopped_reason,
        }


class ResearchAgent:
    def __init__(
        self,
        data: MarketData,
        registry: ExperimentRegistry,
        budget: ResearchBudget = ResearchBudget(),
        horizon: int = 1,
        train_fraction: float = 0.6,
        valid_fraction: float = 0.2,
        criteria: PromotionCriteria = PromotionCriteria(),
        seed: int = 0,
        ai_provider=None,
        n_ai_candidates: int = 2,
    ):
        self.data = data
        self.registry = registry
        self.budget = budget
        self.horizon = horizon
        self.criteria = criteria
        self.seed = seed
        # Optional LLM provider (mock or Anthropic). When set, the agent asks it
        # for a few structured-JSON candidates per run; every proposal still goes
        # through the same causal-validation pipeline as any other factor.
        self.ai_provider = ai_provider
        self.n_ai_candidates = n_ai_candidates
        # Development window = train + validation. The locked test (the remainder)
        # is never handed to the agent.
        split = split_by_fraction(data.index, train_fraction, valid_fraction)
        dev_mask = data.index <= split.valid_end
        self.dev_data = data.subset(pd.Series(dev_mask, index=data.index))
        self._valid_end = split.valid_end

    # -- family selection ----------------------------------------------------
    def choose_family(self, families: list[str] | None = None) -> tuple[str, dict[str, int]]:
        families = families or list(TEMPLATES)
        counts = {f: self.registry.family_trial_count(f) for f in families}
        # explore the least-explored family first
        family = min(counts, key=lambda f: counts[f])
        return family, counts

    # -- candidate proposal --------------------------------------------------
    def _screen_ic(self, spec: FactorSpec) -> float:
        try:
            ic = ic_series(compute_factor(spec, self.dev_data), self.dev_data.forward_returns(self.horizon))
            return float(ic.mean()) if len(ic) else 0.0
        except Exception:
            return 0.0

    def _propose(self, family: str, room: int) -> list[FactorSpec]:
        """Seed with templates, then mutate the most promising near-misses.

        Mutation is bounded by both the remaining candidate budget (``room``) and
        ``max_mutations_per_lineage``.
        """
        seeds = [s for s in generate_templates(which=[family])]
        seeds = seeds[:room]
        # screen seeds on the development window and mutate the best few
        scored = sorted(seeds, key=lambda s: abs(self._screen_ic(s)), reverse=True)
        proposed = list(seeds)
        proposed.extend(self._propose_ai(family, room - len(proposed)))
        remaining = room - len(proposed)
        for parent in scored[:2]:
            if remaining <= 0:
                break
            muts = mutate_family(parent)[: min(self.budget.max_mutations_per_lineage, remaining)]
            # keep only mutations that actually differ and aren't already seeded
            existing = {s.expression_hash for s in proposed}
            muts = [m for m in muts if m.expression_hash not in existing]
            proposed.extend(muts)
            remaining = room - len(proposed)
        # de-dup by expression hash, preserve order
        seen: set[str] = set()
        unique: list[FactorSpec] = []
        for s in proposed:
            if s.expression_hash not in seen:
                seen.add(s.expression_hash)
                unique.append(s)
        return unique[:room]

    def _propose_ai(self, family: str, room: int) -> list[FactorSpec]:
        """Ask the LLM provider for a bounded number of validated candidates.

        AI proposals are best-effort: malformed JSON, a schema miss, a refusal,
        or a non-causal expression is caught and skipped, never crashing the run.
        """
        if self.ai_provider is None or room <= 0:
            return []
        out: list[FactorSpec] = []
        context = (
            f"Family under study: {family}. Propose a distinct cross-sectional "
            f"equity factor in this family that may survive costs."
        )
        for i in range(min(self.n_ai_candidates, room)):
            try:
                spec = generate_ai(f"{context} (idea #{i})", provider=self.ai_provider)
                out.append(spec)
            except Exception:
                continue
        return out

    # -- main loop -----------------------------------------------------------
    def run(self, families: list[str] | None = None) -> AgentRunReport:
        family, counts = self.choose_family(families)
        governor = HoldoutGovernor(self.registry, family, self.budget)

        prior = self.registry.family_trial_count(family)
        room = max(0, self.budget.max_candidates - prior)
        if room == 0:
            return AgentRunReport(
                family, counts, 0, [], [], [], self.budget.max_candidates,
                self.registry.holdout_access_count(family),
                "candidate budget already exhausted",
            )

        specs = self._propose(family, room)
        # hard stop: never exceed the budget
        try:
            governor.check_candidate_budget()
        except Exception:
            specs = []

        study = run_family_study(
            family, specs, self.dev_data, self.registry,
            horizon=self.horizon, criteria=self.criteria, seed=self.seed,
        )

        rejected = [r.spec.factor_id for r in study.results if r.report.get("decision", "").startswith("rejected")]
        duplicates = [r.spec.factor_id for r in study.results if r.report.get("decision") == DecisionState.DUPLICATE.value]
        holdout = self.registry.holdout_access_count(family)
        assert holdout == 0, "invariant violated: agent must never access the locked test"

        return AgentRunReport(
            family=family,
            families_considered=counts,
            n_candidates_evaluated=len(study.results),
            survivors=study.survivors,
            rejected=rejected,
            duplicates=duplicates,
            budget_candidates=self.budget.max_candidates,
            holdout_accesses=holdout,
            stopped_reason="budget reached" if len(specs) >= room else "search space exhausted",
            study=study,
        )


__all__ = ["ResearchAgent", "AgentRunReport"]
