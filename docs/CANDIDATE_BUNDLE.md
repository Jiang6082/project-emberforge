# Candidate Bundle — the offline export format

The candidate bundle is the **only** channel from Emberforge to Project Geld: a
manual, versioned, offline, checksummed directory. There are no API calls, shared
databases, or hooks. Exporting requires an explicit **human-approved** decision
state — `export_candidate(..., approved=True)` raises `ApprovalError` otherwise.

## Layout

```
candidate_bundle/
    manifest.json          # schema version, approval state, source commit, file list
    factor.json            # immutable declarative expression + hash + inputs
    hypothesis.md          # economic hypothesis
    evaluation.json        # metrics + adjusted statistics + trial/holdout counts
    lineage.json           # ancestor experiment chain
    data_provenance.json   # dataset fingerprint, source, feed, frequency, universe
    report.md              # the human-readable candidate report
    checksums.txt          # SHA-256 of every other file
```

## `factor.json` is declarative and immutable

```json
{
  "schema_version": "1.0.0",
  "candidate_id": "momentum_20",
  "expression": "ts_returns(close, 20)",
  "canonical_expression": "ts_returns(close,20)",
  "expression_hash": "125968046f689a2dee4f31144ed32347",
  "required_fields": ["close"],
  "intended_frequency": "daily",
  "max_lookback": 20,
  "expected_sign": 1,
  "complexity_score": 7
}
```

No executable Python appears anywhere in the bundle. v1 is strictly declarative;
a future version may support *signed, reviewed* plugins (see ROADMAP).

## Integrity

`export.verify_bundle(dir)` recomputes every checksum and reports mismatches or
missing files. `checksums.txt` covers all files except itself. The demo asserts
`checksums_ok is True` after export, and `tests/test_export.py` proves that
tampering with any file breaks verification.

## Designed for a future Geld validator

The schema is intentionally simple and self-describing so a validator *could* be
written on the Geld side later — but **no such validator exists in Geld today**,
and Emberforge never modifies Geld. Consumption is a manual, human-in-the-loop
step.

## Fields in `manifest.json`

`schema_version, candidate_id, expression_hash, source_project, source_commit,
source_dirty, created_at, approval_state, universe_assumptions, preprocessing,
known_limitations, nearest_duplicates, files`.
