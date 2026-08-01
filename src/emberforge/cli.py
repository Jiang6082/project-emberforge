"""Emberforge command-line interface.

Scriptable subcommands mirroring the research workflow. Everything runs offline
against synthetic data by default; nothing here can place a trade or touch
Project Geld.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__


def _load_data(args):
    from .data import load_csv_dir, make_synthetic

    if getattr(args, "csv_dir", None):
        return load_csv_dir(args.csv_dir)
    return make_synthetic(seed=getattr(args, "seed", 7))


def cmd_data_validate(args) -> int:
    data = _load_data(args)
    print(json.dumps({
        "symbols": len(data.symbols), "rows": len(data.index),
        "frequency": data.metadata.frequency, "feed": data.metadata.feed,
        "fingerprint": data.metadata.fingerprint,
        "start": data.metadata.start, "end": data.metadata.end,
    }, indent=2))
    return 0


def cmd_factor_validate(args) -> int:
    from .dsl import make_factor

    try:
        spec = make_factor("cli_factor", args.expression)
    except Exception as exc:
        print(f"INVALID: {exc}")
        return 1
    print(json.dumps({
        "valid": True, "canonical": spec.canonical_expression,
        "hash": spec.expression_hash, "required_fields": list(spec.required_fields),
        "max_lookback": spec.max_lookback, "complexity": spec.complexity_score,
    }, indent=2))
    return 0


def cmd_factor_evaluate(args) -> int:
    from .analytics import evaluate_factor
    from .dsl import make_factor

    data = _load_data(args)
    spec = make_factor("cli_factor", args.expression)
    ev = evaluate_factor(spec, data, horizon=args.horizon)
    print(json.dumps(ev.to_metrics(), indent=2, default=str))
    return 0


def cmd_factor_compare(args) -> int:
    from .compute import compute_factor
    from .dedup import score_correlation
    from .dsl import make_factor

    data = _load_data(args)
    a = compute_factor(make_factor("a", args.a), data)
    b = compute_factor(make_factor("b", args.b), data)
    corr, overlap = score_correlation(a, b)
    print(json.dumps({"correlation": corr, "overlap": overlap}, indent=2))
    return 0


def cmd_generate_templates(args) -> int:
    from .generate import generate_templates

    specs = generate_templates()
    for s in specs:
        print(f"{s.factor_id}\t{s.expression}\t[{s.expression_hash}]")
    return 0


def cmd_experiment_list(args) -> int:
    from .registry import ExperimentRegistry

    reg = ExperimentRegistry(args.registry)
    for row in reg.list(family=args.family, status=args.status):
        print(f"{row['experiment_id']}\t{row['status']:>24}\t{row['factor_id']}\t{row['expression']}")
    return 0


def cmd_experiment_show(args) -> int:
    from .registry import ExperimentRegistry

    reg = ExperimentRegistry(args.registry)
    row = reg.get(args.experiment_id)
    if not row:
        print("not found")
        return 1
    print(json.dumps(row, indent=2, default=str))
    return 0


def cmd_factor_robustness(args) -> int:
    from .dsl import make_factor
    from .robustness import robustness_report

    data = _load_data(args)
    spec = make_factor("cli_factor", args.expression)
    tmpl = args.template if getattr(args, "template", None) else None
    params = [int(p) for p in args.params.split(",")] if getattr(args, "params", None) else None
    rep = robustness_report(spec, data, horizon=args.horizon,
                            sensitivity_template=tmpl, sensitivity_params=params)
    print(json.dumps(rep.summary(), indent=2, default=str))
    return 0


def cmd_research_agent_run(args) -> int:
    from .agent import ResearchAgent
    from .data import make_synthetic
    from .registry import ExperimentRegistry
    from .registry.holdout import ResearchBudget

    data = make_synthetic(seed=args.seed, n_days=args.n_days)
    reg = ExperimentRegistry(args.registry)
    provider = None
    if getattr(args, "ai", None) == "mock":
        from .generate import MockProvider

        provider = MockProvider()
    elif getattr(args, "ai", None) == "anthropic":
        from .generate import AnthropicProvider

        provider = AnthropicProvider(model=args.ai_model)
    agent = ResearchAgent(data, reg, budget=ResearchBudget(max_candidates=args.budget),
                          seed=args.seed, ai_provider=provider)
    families = args.families.split(",") if args.families else None
    report = agent.run(families=families)
    print(json.dumps(report.summary(), indent=2, default=str))
    return 0


def cmd_demo(args) -> int:
    from .demo import run_demo

    summary = run_demo(out_dir=args.out)
    print(json.dumps(summary, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emberforge", description="Emberforge factor research CLI")
    p.add_argument("--version", action="version", version=f"emberforge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_data_opts(sp):
        sp.add_argument("--csv-dir", default=None, help="load CSV panels instead of synthetic data")
        sp.add_argument("--seed", type=int, default=7)

    d = sub.add_parser("data", help="data commands").add_subparsers(dest="sub", required=True)
    dv = d.add_parser("validate"); add_data_opts(dv); dv.set_defaults(func=cmd_data_validate)

    f = sub.add_parser("factor", help="factor commands").add_subparsers(dest="sub", required=True)
    fv = f.add_parser("validate"); fv.add_argument("expression"); fv.set_defaults(func=cmd_factor_validate)
    fe = f.add_parser("evaluate"); fe.add_argument("expression"); fe.add_argument("--horizon", type=int, default=1)
    add_data_opts(fe); fe.set_defaults(func=cmd_factor_evaluate)
    fc = f.add_parser("compare"); fc.add_argument("a"); fc.add_argument("b"); add_data_opts(fc)
    fc.set_defaults(func=cmd_factor_compare)
    fr = f.add_parser("robustness"); fr.add_argument("expression"); fr.add_argument("--horizon", type=int, default=1)
    fr.add_argument("--template", default=None, help="sensitivity template with {w}")
    fr.add_argument("--params", default=None, help="comma-separated integer params")
    add_data_opts(fr); fr.set_defaults(func=cmd_factor_robustness)

    g = sub.add_parser("generate", help="generation commands").add_subparsers(dest="sub", required=True)
    gt = g.add_parser("templates"); gt.set_defaults(func=cmd_generate_templates)

    e = sub.add_parser("experiment", help="registry commands").add_subparsers(dest="sub", required=True)
    el = e.add_parser("list"); el.add_argument("--registry", default="runtime/demo/registry.sqlite3")
    el.add_argument("--family", default=None); el.add_argument("--status", default=None)
    el.set_defaults(func=cmd_experiment_list)
    es = e.add_parser("show"); es.add_argument("experiment_id")
    es.add_argument("--registry", default="runtime/demo/registry.sqlite3"); es.set_defaults(func=cmd_experiment_show)

    ra = sub.add_parser("research-agent", help="constrained research agent").add_subparsers(dest="sub", required=True)
    rar = ra.add_parser("run")
    rar.add_argument("--registry", default="runtime/agent/registry.sqlite3")
    rar.add_argument("--families", default=None, help="comma-separated families to consider")
    rar.add_argument("--budget", type=int, default=40)
    rar.add_argument("--seed", type=int, default=7)
    rar.add_argument("--n-days", dest="n_days", type=int, default=400)
    rar.add_argument("--ai", choices=["mock", "anthropic"], default=None,
                     help="also propose LLM-generated candidates (mock = offline)")
    rar.add_argument("--ai-model", default="claude-opus-5")
    rar.set_defaults(func=cmd_research_agent_run)

    dm = sub.add_parser("demo", help="run the end-to-end demonstration")
    dm.add_argument("--out", default="runtime/demo"); dm.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
