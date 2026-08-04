"""Cross-check: does an Emberforge bundle pass Project Geld's *real* validator?

Emberforge never imports Geld in its package. This standalone script loads Geld's
``geld/candidates/validator.py`` directly by file path (read-only; the file is
dependency-free and side-effect-free) and runs it against Emberforge-produced
``candidate_bundle_v1`` JSON files, proving the offline hand-off actually works.

Usage:
    python examples/verify_against_geld.py [geld_bundles_dir] [path/to/project-geld]
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLES = HERE.parent / "runtime" / "pipeline" / "geld_bundles"
DEFAULT_GELD = HERE.parents[1] / "project-geld"


def _load_geld_validator(geld_root: Path):
    vpath = geld_root / "geld" / "candidates" / "validator.py"
    if not vpath.exists():
        raise SystemExit(f"[skip] Geld validator not found at {vpath}")
    spec = importlib.util.spec_from_file_location("geld_validator_readonly", vpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # needed so @dataclass can introspect
    spec.loader.exec_module(mod)          # pure module: only defines constants + functions
    return mod


def main() -> int:
    bundles = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BUNDLES
    geld_root = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_GELD
    validator = _load_geld_validator(geld_root)

    files = sorted(bundles.glob("*.candidate.json"))
    if not files:
        print(f"[skip] no *.candidate.json in {bundles} — run 'emberforge pipeline run' first")
        return 0

    all_ok = True
    for f in files:
        bundle = json.loads(f.read_text())
        result = validator.validate_bundle(bundle)
        status = "OK  " if result.ok else "FAIL"
        print(f"[{status}] {f.name}  (candidate_id={result.candidate_id})")
        for w in result.warnings:
            print(f"        warn: {w}")
        for e in result.errors:
            print(f"        error: {e}")
        all_ok = all_ok and result.ok

    print("\nAll Emberforge bundles pass Geld's real validator." if all_ok
          else "\nSome bundles were rejected — see errors above.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
