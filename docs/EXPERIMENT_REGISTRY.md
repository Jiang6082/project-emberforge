# Experiment Registry, Lineage & Holdout Governance

A SQLite registry (`emberforge.registry.ExperimentRegistry`) records **every**
experiment — including failures and duplicates. Nothing is ever deleted for
performing poorly.

## What every experiment records

`experiment_id, parent_id, family, factor_id, expression, expression_hash,
generator, created_at, git_commit, git_dirty, command, config_json,
dataset_fingerprint, universe_fingerprint, seed, train_end, valid_end, status,
failure_reason, holdout_viewed, llm_model, prompt_hash, metrics_json,
artifacts_json`.

Git provenance (`git_commit`, `git_dirty`) is captured automatically via
`registry/gitinfo.py`.

## Status lifecycle

```
generated → invalid
          → evaluated → duplicate
                      → rejected_in_development
                      → rejected_after_robustness
                      → research_survivor → human_approved → exported
                      → superseded
```

## Trial counts drive the statistics

`family_trial_count(family)` returns the number of experiments recorded in a
search family. This count is the **source of truth** consumed by:

* the Deflated Sharpe expected-maximum penalty (more trials ⇒ higher bar);
* the number of hypotheses in the Benjamini–Hochberg / Holm adjustments.

Because failures are recorded *before* the statistics run, a candidate that only
looks good after many attempts is correctly penalized.

## Lineage

`lineage(experiment_id)` walks `parent_id` from root to the given experiment, so
a mutated candidate's full edit history is reconstructable. Mutations set
`parent_ids` on the child `FactorSpec`, which the pipeline records as `parent_id`.

```bash
emberforge experiment list  --registry runtime/demo/registry.sqlite3 --family momentum_family
emberforge experiment show  <experiment_id> --registry runtime/demo/registry.sqlite3
```

## Holdout governance

`registry/holdout.py` provides:

* `DataSplit` / `split_by_fraction` — development / validation / locked-test
  (and optional forward) partitions.
* `HoldoutGovernor` — enforces a `ResearchBudget`:
  * `check_candidate_budget()` blocks once a family exhausts its candidate budget;
  * `access_locked_test()` records each locked-test view, warns on repeat access,
    and (with `hard=True`) raises `BudgetExceeded` past the cap.

Every locked-test access is written to a `holdout_access` table and flips the
experiment's `holdout_viewed` flag. After the locked test is viewed, results
derived from it are no longer "untouched validation" and belong to a new
generation.
