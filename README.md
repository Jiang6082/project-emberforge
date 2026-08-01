# Project Emberforge

Emberforge is an **AI-assisted factor-research platform with false-discovery
control**. It generates candidate factors, computes them causally, evaluates
their statistical and economic behavior, controls for multiple testing and
selection bias, and exports human-approved candidates as offline, checksummed
bundles.

> Emberforge is a **research system, not a trading bot.** It never places orders,
> never requires credentials, and communicates with Project Geld only through a
> manual, one-way, offline bundle. See
> [`docs/PROJECT_GELD_INTERFACE_NOTES.md`](docs/PROJECT_GELD_INTERFACE_NOTES.md).

## The guiding principle

The goal is **not** to search until a high Sharpe appears — it is to make it hard
to fool ourselves. Every candidate, failed experiment, mutation, and holdout
access is recorded. A factor that looks good after 24 attempts is treated
differently from one specified once and validated cleanly. See
[`docs/SCIENTIFIC_METHOD.md`](docs/SCIENTIFIC_METHOD.md).

## Install

```bash
cd project-emberforge
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

No paid data and no LLM API key are required. The default provider for
AI-assisted generation is a deterministic offline mock.

## Run the tests

```bash
pytest
```

## Run the end-to-end demo

```bash
python -m emberforge.demo
# or
emberforge demo --out runtime/demo
```

The demo generates a known momentum factor plus duplicates and noise factors,
evaluates them, detects duplicates, applies multiple-testing corrections, rejects
the weak/duplicate candidates, retains one **research survivor**, writes reports,
and exports one human-approved bundle. Crucially, it records **everything tried**,
not just the winner:

```
runtime/demo/
    registry.sqlite3          # every experiment, including failures
    reports/<factor>.md|.json # per-candidate reports
    family_report.md          # aggregate dashboard (raw vs adjusted evidence)
    candidate_bundle/         # the one exported, checksummed survivor
    summary.json
```

## CLI

```bash
emberforge data validate
emberforge factor validate "ts_returns(close, 20)"
emberforge factor evaluate "ts_returns(close, 20)" --horizon 1
emberforge factor compare "ts_returns(close,20)" "ts_delta(close,20)"
emberforge generate templates
emberforge experiment list --registry runtime/demo/registry.sqlite3
emberforge experiment show <experiment_id> --registry runtime/demo/registry.sqlite3
emberforge demo
```

## Documentation

| Doc | Contents |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module map and data flow |
| [SCIENTIFIC_METHOD.md](docs/SCIENTIFIC_METHOD.md) | Anti-self-deception design |
| [FACTOR_DSL.md](docs/FACTOR_DSL.md) | The declarative factor language |
| [EXPERIMENT_REGISTRY.md](docs/EXPERIMENT_REGISTRY.md) | Lineage, trial counts, holdout governance |
| [MULTIPLE_TESTING.md](docs/MULTIPLE_TESTING.md) | BH, Holm, Deflated Sharpe, PBO, bootstrap |
| [AI_RESEARCH_AGENT.md](docs/AI_RESEARCH_AGENT.md) | AI generation & constrained agent (Phase B) |
| [PROJECT_GELD_INTERFACE_NOTES.md](docs/PROJECT_GELD_INTERFACE_NOTES.md) | What Geld actually is; the boundary |
| [CANDIDATE_BUNDLE.md](docs/CANDIDATE_BUNDLE.md) | The offline export format |
| [ROADMAP.md](docs/ROADMAP.md) | Phase B and beyond |
| [IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) | Build summary & acceptance evidence |

## License

MIT.
