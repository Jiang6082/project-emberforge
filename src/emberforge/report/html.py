"""Self-contained HTML research dashboard.

One static HTML file (inline CSS, no assets, no JS dependencies) that a human
opens in a browser after each run. It ranks every candidate, colour-codes the
decision, highlights survivors, and — crucially — keeps *raw* metrics visually
separate from *selection-bias-adjusted* evidence, so nobody mistakes a shiny
Sharpe for a validated edge.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime


def _fmt(x, nd=3):
    try:
        if x is None or x != x:
            return "—"
        return f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return html.escape(str(x))


_DECISION_CLASS = {
    "research_survivor": "survivor",
    "human_approved": "survivor",
    "auto_approved": "survivor",
    "exported": "survivor",
    "duplicate": "dup",
    "invalid": "rej",
    "rejected_in_development": "rej",
    "rejected_after_robustness": "rej",
}

_CSS = """
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:#f7f7f9;color:#1c1e21}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
h1{margin:0 0 4px;font-size:22px}
.sub{color:#606770;margin:0 0 18px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 20px}
.card{background:#fff;border:1px solid #e4e6eb;border-radius:10px;padding:12px 16px;min-width:120px}
.card .n{font-size:22px;font-weight:700}
.card .l{color:#606770;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.note{background:#fff8e1;border:1px solid #ffe08a;border-radius:8px;padding:10px 14px;margin:0 0 18px;color:#6b5900;font-size:13px}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e4e6eb;border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid #eef0f2;white-space:nowrap}
th{background:#fafbfc;font-size:12px;color:#606770;text-transform:uppercase;letter-spacing:.02em;position:sticky;top:0}
td.l,th.l{text-align:left}
tr:last-child td{border-bottom:none}
.grp-raw{background:#f4f8ff}.grp-adj{background:#f2fbf4}
th.grp-raw,th.grp-adj{background:#eaf1fb}
tr.survivor td.l:first-child{border-left:4px solid #2e7d32}
tr.dup td.l:first-child{border-left:4px solid #9aa0a6}
tr.rej td.l:first-child{border-left:4px solid #d5d7db}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600}
.badge.survivor{background:#e6f4ea;color:#1e7e34}
.badge.dup{background:#eceff1;color:#546e7a}
.badge.rej{background:#fbeaea;color:#b23b3b}
.yes{color:#1e7e34;font-weight:600}.no{color:#b23b3b}
.legend{margin:14px 0 0;color:#606770;font-size:12px}
.legend b.raw{color:#2f6fd0}.legend b.adj{color:#1e7e34}
footer{margin-top:18px;color:#8a8d91;font-size:12px}
"""


def _bool_cell(v):
    if v is True:
        return '<td class="grp-adj"><span class="yes">yes</span></td>'
    if v is False:
        return '<td class="grp-adj"><span class="no">no</span></td>'
    return '<td class="grp-adj">—</td>'


def family_report_html(title: str, rows: list[dict], meta: dict | None = None) -> str:
    meta = meta or {}
    survivors = [r["factor_id"] for r in rows if r.get("decision") == "research_survivor"]

    def _key(r):
        s = r.get("statistics", {})
        return (s.get("fdr_reject") is True, -(s.get("p_fdr") or 1.0))

    ordered = sorted(rows, key=_key, reverse=True)

    header_cells = [
        ('l', "Factor"), ('l', "Family"), ('l', "Decision"),
        ('grp-raw', "mean IC"), ('grp-raw', "IC t"), ('grp-raw', "LS Sharpe"), ('grp-raw', "turnover"),
        ('grp-adj', "BH p"), ('grp-adj', "survives FDR"), ('grp-adj', "DSR"),
        ('grp-adj', "PBO CSCV"), ('grp-adj', "White p"), ('grp-adj', "SPA p"),
    ]
    thead = "".join(f'<th class="{c}">{html.escape(t)}</th>' for c, t in header_cells)

    body = []
    for r in ordered:
        m = r.get("metrics", {})
        s = r.get("statistics", {})
        cls = _DECISION_CLASS.get(r.get("decision"), "")
        body.append(
            f'<tr class="{cls}">'
            f'<td class="l"><code>{html.escape(str(r.get("factor_id","")))}</code></td>'
            f'<td class="l">{html.escape(str(r.get("family","")))}</td>'
            f'<td class="l"><span class="badge {cls}">{html.escape(str(r.get("decision","")))}</span></td>'
            f'<td class="grp-raw">{_fmt(m.get("mean_ic"),4)}</td>'
            f'<td class="grp-raw">{_fmt(m.get("ic_t_stat"),2)}</td>'
            f'<td class="grp-raw">{_fmt(m.get("sharpe"),2)}</td>'
            f'<td class="grp-raw">{_fmt(m.get("turnover"),2)}</td>'
            f'<td class="grp-adj">{_fmt(s.get("p_fdr"),4)}</td>'
            f'{_bool_cell(s.get("fdr_reject"))}'
            f'<td class="grp-adj">{_fmt(s.get("dsr"),2)}</td>'
            f'<td class="grp-adj">{_fmt(s.get("pbo"),2)}</td>'
            f'<td class="grp-adj">{_fmt(s.get("white_rc_p"),2)}</td>'
            f'<td class="grp-adj">{_fmt(s.get("spa_p"),2)}</td>'
            '</tr>'
        )

    cards = [
        ("candidates", len(rows)),
        ("survivors", len(survivors)),
        ("families", len({r.get("family") for r in rows})),
        ("trials (family)", meta.get("trial_count", len(rows))),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="n">{html.escape(str(n))}</div><div class="l">{html.escape(l)}</div></div>'
        for l, n in cards
    )

    generated = meta.get("generated_at") or datetime.now(UTC).isoformat(timespec="seconds")
    survivors_line = ", ".join(f"<code>{html.escape(x)}</code>" for x in survivors) or "none"
    data_note = html.escape(str(meta.get("data", "")))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Emberforge — {html.escape(title)}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<h1>Emberforge research report — {html.escape(title)}</h1>
<p class="sub">Generated {html.escape(generated)}{(' · ' + data_note) if data_note else ''} · Survivors: {survivors_line}</p>
<div class="cards">{cards_html}</div>
<div class="note"><b>Read this right:</b> the blue columns are <b>raw</b> metrics; the green columns are
<b>selection-bias-adjusted</b> evidence. Promotion is based on the adjusted evidence, never the raw Sharpe.
Failed and duplicate candidates are kept on purpose — the record of what was tried is what makes a survivor trustworthy.</div>
<table><thead><tr>{thead}</tr></thead><tbody>
{''.join(body)}
</tbody></table>
<p class="legend"><b class="raw">Raw</b>: as-measured on all data. <b class="adj">Adjusted</b>: penalized for how many
factors were tried (Benjamini–Hochberg FDR, Deflated Sharpe, PBO, White's Reality Check, Hansen's SPA).</p>
<footer>Emberforge is a research system, not a trading bot. No output here is a validated live strategy.</footer>
</div></body></html>
"""


__all__ = ["family_report_html"]
