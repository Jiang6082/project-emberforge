"""Standalone candidate-bundle validator — the check Project Geld can run.

``verify_bundle`` (in :mod:`bundle`) only confirms the SHA-256 checksums. This
validator goes further: it *independently* re-parses the exported factor
expression, re-runs the causality/structure checks, recomputes the canonical form
and hash, confirms the schema version and the human-approval state. It imports
only Emberforge's DSL — no market data, no network — so Geld (or any reviewer)
can drop it in to vet a bundle before trusting it, closing the one-way boundary
loop described in ``docs/CANDIDATE_BUNDLE.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..dsl import canonical, causality, parser
from .bundle import BUNDLE_SCHEMA_VERSION, verify_bundle

SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0.0"})


@dataclass
class BundleValidation:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {"ok": self.ok, "checks": self.checks, "problems": self.problems}


def validate_bundle(bundle_dir: str | Path) -> BundleValidation:
    """Independently validate a candidate bundle. Never trusts the bundle's own
    ``expression_hash``/``canonical_expression`` — it recomputes them."""
    out = Path(bundle_dir)
    checks: dict[str, bool] = {}
    problems: list[str] = []

    def fail(name: str, msg: str) -> None:
        checks[name] = False
        problems.append(msg)

    # 1) required files present
    required = ["manifest.json", "factor.json", "checksums.txt"]
    missing = [f for f in required if not (out / f).exists()]
    if missing:
        fail("files_present", f"missing bundle files: {missing}")
        return BundleValidation(False, checks, problems)
    checks["files_present"] = True

    # 2) checksum integrity (delegates to the existing verifier)
    ck_ok, ck_problems = verify_bundle(out)
    checks["checksums_ok"] = ck_ok
    if not ck_ok:
        problems.extend(ck_problems)

    # 3) load JSON payloads
    try:
        factor = json.loads((out / "factor.json").read_text())
        manifest = json.loads((out / "manifest.json").read_text())
    except json.JSONDecodeError as e:
        fail("json_parses", f"bundle JSON is invalid: {e}")
        return BundleValidation(False, checks, problems)
    checks["json_parses"] = True

    # 4) schema version supported (check both factor and manifest)
    versions = {factor.get("schema_version"), manifest.get("schema_version")}
    if not versions <= SUPPORTED_SCHEMA_VERSIONS:
        fail("schema_supported",
             f"unsupported schema version(s) {versions}; supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)} "
             f"(this validator targets {BUNDLE_SCHEMA_VERSION})")
    else:
        checks["schema_supported"] = True

    # 5) human-approval state
    if manifest.get("approval_state") != "human_approved":
        fail("human_approved",
             f"approval_state is {manifest.get('approval_state')!r}, expected 'human_approved'")
    else:
        checks["human_approved"] = True

    # 6) the declarative expression must independently parse and be causal
    expression = factor.get("expression")
    tree = None
    if not isinstance(expression, str) or not expression.strip():
        fail("expression_parses", "factor.json has no non-empty 'expression'")
    else:
        try:
            tree = parser.parse(expression)
            checks["expression_parses"] = True
        except Exception as e:
            fail("expression_parses", f"expression failed to parse: {e}")

    if tree is not None:
        try:
            causality.validate(tree)          # structure (arity/ops/limits)
            causality.check_causality(tree)    # no look-ahead
            checks["expression_causal"] = True
        except Exception as e:
            fail("expression_causal", f"expression failed causality/structure checks: {e}")

        # 7) recompute canonical form + hash and compare to what was shipped
        recomputed_canon = canonical.canonical_string(tree)
        recomputed_hash = canonical.factor_hash(tree)
        if factor.get("canonical_expression") != recomputed_canon:
            fail("canonical_matches",
                 f"canonical_expression mismatch: shipped {factor.get('canonical_expression')!r} "
                 f"vs recomputed {recomputed_canon!r}")
        else:
            checks["canonical_matches"] = True
        if factor.get("expression_hash") != recomputed_hash:
            fail("hash_matches",
                 f"expression_hash mismatch: shipped {factor.get('expression_hash')!r} "
                 f"vs recomputed {recomputed_hash!r}")
        else:
            checks["hash_matches"] = True
        # the manifest's hash must agree with the factor's
        if manifest.get("expression_hash") not in (None, recomputed_hash):
            fail("manifest_hash_matches",
                 "manifest expression_hash disagrees with the recomputed hash")
        else:
            checks["manifest_hash_matches"] = True

    ok = all(checks.values()) and not problems
    return BundleValidation(ok, checks, problems)


__all__ = ["validate_bundle", "BundleValidation", "SUPPORTED_SCHEMA_VERSIONS"]
