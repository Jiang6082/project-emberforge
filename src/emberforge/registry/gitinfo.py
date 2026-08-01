"""Best-effort git provenance capture for reproducibility."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def git_provenance(cwd: str | Path | None = None) -> dict:
    root = Path(cwd) if cwd else Path.cwd()
    commit = _run(["git", "rev-parse", "HEAD"], root)
    status = _run(["git", "status", "--porcelain"], root)
    dirty = None if status is None else bool(status.strip())
    return {"git_commit": commit, "git_dirty": dirty}
