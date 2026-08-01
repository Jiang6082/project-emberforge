"""Reporting: per-candidate reports and an aggregate research dashboard."""

from __future__ import annotations

from .candidate import candidate_report_dict, candidate_report_md


def _fmt(x, nd=3):
    try:
        if x is None or x != x:
            return "n/a"
        return f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def family_report_md(title: str, rows: list[dict]) -> str:
    """Aggregate dashboard ranking candidates, separating raw from adjusted evidence."""
    header = [
        f"# Research family report — {title}",
        "",
        f"Total candidates recorded: **{len(rows)}** (including failures and duplicates).",
        "",
        "> Ranked by adjusted evidence. Raw metrics are shown but are **not** the basis for promotion.",
        "",
        "| factor | family | decision | mean IC | IC t | LS Sharpe | BH p | survives FDR | DSR |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    def _key(r):
        s = r.get("statistics", {})
        return (s.get("fdr_reject") is True, -(s.get("p_fdr") or 1.0))
    for r in sorted(rows, key=_key, reverse=True):
        m = r["metrics"]; s = r.get("statistics", {})
        header.append(
            f"| `{r['factor_id']}` | {r['family']} | {r['decision']} | "
            f"{_fmt(m['mean_ic'],4)} | {_fmt(m['ic_t_stat'],2)} | {_fmt(m['sharpe'],2)} | "
            f"{_fmt(s.get('p_fdr'),4)} | {s.get('fdr_reject')} | {_fmt(s.get('dsr'),2)} |"
        )
    survivors = [r for r in rows if r["decision"] == "research_survivor"]
    header += [
        "",
        f"**Survivors:** {', '.join(r['factor_id'] for r in survivors) or 'none'}.",
        "",
        "Failed and duplicate candidates are retained above and in the experiment registry "
        "by design — the record of what was tried is what makes the survivor interpretable.",
    ]
    return "\n".join(header)


__all__ = ["candidate_report_dict", "candidate_report_md", "family_report_md"]
