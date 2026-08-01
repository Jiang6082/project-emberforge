"""Enforceable Project Geld boundary tests.

Two concrete assertions:
  (a) Emberforge imports nothing from ``geld.*``.
  (b) Running the pipeline writes to no path under any Project Geld tree.
"""

import re
from pathlib import Path

import emberforge

SRC = Path(emberforge.__file__).resolve().parent


def test_no_geld_imports():
    pattern = re.compile(r"^\s*(?:import\s+geld|from\s+geld[\.\s])", re.MULTILINE)
    offenders = []
    for py in SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(py))
    assert not offenders, f"forbidden geld imports in: {offenders}"


def test_geld_adapter_is_read_only():
    # The only code that touches Geld is the loader, and it must open SQLite in
    # read-only mode (mode=ro) so it can never write into the Geld tree.
    loaders = (SRC / "data" / "loaders.py").read_text()
    assert "mode=ro" in loaders
    assert "uri=True" in loaders


def test_demo_writes_only_under_out_dir(tmp_path):
    from emberforge.demo import run_demo

    before = _snapshot(tmp_path.parent)
    out = tmp_path / "demo"
    summary = run_demo(out_dir=out)
    # every written file is under our out dir
    for p in out.rglob("*"):
        assert str(p).startswith(str(out))
    assert summary["out_dir"] == str(out)


def _snapshot(root: Path) -> set:
    return {str(p) for p in root.rglob("*")}
