# Synthetic demo snapshot

Recorded September 13, 2026 with Python 3.12 on Windows, using the implementation at [`f5bfeb4`](https://github.com/Jiang6082/project-emberforge/tree/f5bfeb4eb6deb8ad1a9de071ceba9f77724684b7). Only documentation was being edited during this run.

```sh
python -m emberforge.demo
```

The command ran without credentials, an LLM provider, or external market data. It completed and wrote `runtime/demo/summary.json`, the experiment registry, reports, and a candidate bundle.

| Recorded output | Value |
| --- | --- |
| Candidates evaluated | 36 |
| Experiments recorded | 36 |
| Survivor | `momentum_20` |
| Candidates classified as duplicates | 24 |
| Rejected candidates | 11 |
| Export checksum verification | Passed; no verification problems reported |
| PBO in this summary | Unavailable (`NaN`); do not interpret it as zero |

One survivor + 24 duplicates + 11 rejections accounts for all 36 candidates. The planted synthetic effect makes this a demonstration of the workflow, not a test of real-world profitability or a guarantee that every statistical component produced an estimate.

The demo passes `approved=True` in its export call. That is a preconfigured demonstration choice, not evidence that a human approved a live research candidate.

To inspect a new run, start with `runtime/demo/summary.json`, `family_report.md`, and `candidate_bundle/checksums.txt`. Counts can change when the configured candidate set changes. This snapshot replaces the README's older 24-candidate description without overwriting the historical project notes or the portfolio's separately labeled recorded results.
