# Continuing on another machine

Everything is on GitHub (`main`, tag `v0.1.0`). To pick up cleanly elsewhere:

```bash
git clone https://github.com/Jiang6082/project-emberforge.git
cd project-emberforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ,llm for the real Anthropic provider
pytest -m "not slow"             # fast sanity check (~30s); `pytest` runs all
```

## What does NOT travel via git (by design) and how to restore it

| Not in git | Why | Restore |
|---|---|---|
| `.venv/` | virtualenv is machine-specific | recreate with the commands above |
| `runtime/` | generated output (bundles, reports, registries) | regenerate: `emberforge demo` or `emberforge pipeline run` |
| `.github/workflows/ci.yml` | the push token lacks the `workflow` scope | the same content is tracked as **`ci.github-workflow.yml`** — enable CI below |

## Enable GitHub Actions CI (optional, one-time)

The CI definition lives at the repo root as `ci.github-workflow.yml`. On a machine
whose `gh`/token has the `workflow` scope:

```bash
gh auth refresh -s workflow            # grant the scope
mkdir -p .github/workflows
cp ci.github-workflow.yml .github/workflows/ci.yml
git add -f .github/workflows/ci.yml
git commit -m "ci: enable GitHub Actions" && git push
```

## Where things are

- **How to use it:** `docs/TUTORIAL.md`
- **Emberforge vs. Geld boundary:** `docs/DIVISION_OF_LABOR.md`, `docs/PROJECT_GELD_INTERFACE_NOTES.md`
- **Geld-submittable bundles:** produced by `emberforge pipeline run` under
  `runtime/pipeline/geld_bundles/` (regenerate anytime); cross-check with
  `python examples/verify_against_geld.py`.
- **Release history:** `CHANGELOG.md`
