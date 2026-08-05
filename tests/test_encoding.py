"""Cross-platform file-encoding guarantees.

The candidate bundle's whole trust model rests on its SHA-256 checksums being
*reproducible* — the same bytes on every machine that produces or validates it.
Text I/O that relies on the platform's default encoding breaks that: a report
containing ``→`` or ``×`` is written as UTF-8 on Linux but cp1252 on Windows (or
fails to encode at all), so the checksum — and the cross-machine Geld hand-off —
silently diverges.

These tests pin the contract:

* a bundle whose human-readable parts contain non-ASCII round-trips byte-for-byte
  and still validates, and
* no text I/O anywhere in the package relies on the platform default encoding
  (caught on *every* platform, including UTF-8-default CI, via
  ``-X warn_default_encoding``).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from emberforge.dsl import make_factor
from emberforge.export import (
    export_candidate,
    from_native_bundle,
    validate_bundle,
    verify_bundle,
)

# A hypothesis/report deliberately full of the exact characters that broke
# Windows cp1252: rightwards arrow, middle dot, multiplication sign, em dash,
# and an accented letter.
NON_ASCII = "Momentum → persistence · 5×20 — café"
ARROW_UTF8 = "→".encode()  # b"\xe2\x86\x92"


def _export_non_ascii(tmp_path):
    spec = make_factor(
        "mom_utf8",
        "ts_returns(close, 20)",
        economic_hypothesis=NON_ASCII,
        expected_sign=1,
    )
    return export_candidate(
        spec,
        tmp_path / "bundle",
        evaluation_metrics={"mean_ic": 0.03},
        statistics={"dsr": 0.7, "fdr_reject": True},
        lineage=[{"factor_id": "mom_utf8"}],
        novelty={"nearest_duplicates": []},
        data_provenance={"dataset_fingerprint": "abc", "universe": ["A", "B"]},
        report_md=f"# report\n\n{NON_ASCII}\n",
        approved=True,
        trial_count=12,
        holdout_views=0,
    )


def test_non_ascii_bundle_is_utf8_on_disk(tmp_path):
    out = _export_non_ascii(tmp_path)
    # The human-readable parts carry the raw non-ASCII bytes (JSON is ASCII-escaped).
    for name in ("hypothesis.md", "report.md"):
        raw = (out / name).read_bytes()
        assert ARROW_UTF8 in raw, f"{name} is not UTF-8 encoded on disk"
        assert raw.decode("utf-8")  # must decode cleanly as UTF-8


def test_non_ascii_bundle_checksums_and_validates(tmp_path):
    out = _export_non_ascii(tmp_path)
    ok, problems = verify_bundle(out)
    assert ok, problems
    assert validate_bundle(out).ok


def test_non_ascii_survives_geld_adapter_roundtrip(tmp_path):
    out = _export_non_ascii(tmp_path)
    bundle = from_native_bundle(out)
    # The economic hypothesis (with its non-ASCII characters) must survive the
    # read → adapt path intact, not get mangled by a cp1252 round-trip.
    assert "→" in bundle["economic_hypothesis"]
    assert "café" in bundle["economic_hypothesis"]


# The guard script: run the whole pipeline (every reader and writer the package
# has) with the interpreter configured to flag any text I/O that omits an explicit
# encoding. EncodingWarning is only *emitted* under -X warn_default_encoding, so
# this catches regressions even where the platform default is already UTF-8.
_GUARD_SCRIPT = textwrap.dedent(
    '''
    import sys, warnings
    # Silence third-party import-time I/O; we only police our own package.
    warnings.simplefilter("ignore", EncodingWarning)
    from pathlib import Path
    from emberforge.data import make_synthetic
    from emberforge.pipeline import run_pipeline
    from emberforge.export import validate_bundle, from_native_bundle

    # From here on, any unqualified text I/O inside emberforge.* is a hard error.
    warnings.filterwarnings("error", category=EncodingWarning, module=r"emberforge(\\..*)?")

    out = Path(sys.argv[1])
    data = make_synthetic(n_symbols=6, n_days=120, seed=3)
    summary = run_pipeline(out, data=data, families=["momentum"], seed=3)
    # Exercise the readers explicitly too, in case nothing was exported.
    for e in summary["exported"]:
        assert validate_bundle(e["dir"]).ok
        from_native_bundle(e["dir"])
    print("ENCODING_GUARD_OK")
    '''
)


@pytest.mark.slow
def test_package_has_no_default_encoding_text_io(tmp_path):
    script = tmp_path / "guard.py"
    script.write_text(_GUARD_SCRIPT, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", str(script), str(tmp_path / "run")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, (
        "package used the platform default text encoding somewhere "
        f"(stdout:\n{proc.stdout}\nstderr:\n{proc.stderr})"
    )
    assert "ENCODING_GUARD_OK" in proc.stdout
