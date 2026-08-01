"""Persistent experiment registry, lineage, and holdout governance (SQLite).

Every experiment is recorded — including failures. Nothing is ever deleted for
performing poorly; that is the whole point. The registry is also the source of
truth for trial counts (per search family) that feed multiple-testing
adjustments, and it tracks every access to the locked holdout.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .gitinfo import git_provenance

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id   TEXT PRIMARY KEY,
    parent_id       TEXT,
    family          TEXT NOT NULL,
    factor_id       TEXT NOT NULL,
    expression      TEXT NOT NULL,
    expression_hash TEXT NOT NULL,
    generator       TEXT,
    created_at      TEXT NOT NULL,
    git_commit      TEXT,
    git_dirty       INTEGER,
    command         TEXT,
    config_json     TEXT,
    dataset_fingerprint TEXT,
    universe_fingerprint TEXT,
    seed            INTEGER,
    train_end       TEXT,
    valid_end       TEXT,
    status          TEXT NOT NULL,
    failure_reason  TEXT,
    holdout_viewed  INTEGER DEFAULT 0,
    llm_model       TEXT,
    prompt_hash     TEXT,
    metrics_json    TEXT,
    artifacts_json  TEXT
);
CREATE TABLE IF NOT EXISTS holdout_access (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    family      TEXT NOT NULL,
    experiment_id TEXT,
    accessed_at TEXT NOT NULL,
    reason      TEXT
);
CREATE INDEX IF NOT EXISTS idx_exp_family ON experiments(family);
CREATE INDEX IF NOT EXISTS idx_exp_hash ON experiments(expression_hash);
"""


@dataclass
class ExperimentRecord:
    factor_id: str
    family: str
    expression: str
    expression_hash: str
    status: str = "generated"
    parent_id: Optional[str] = None
    generator: str = "manual"
    command: str = ""
    config: dict = field(default_factory=dict)
    dataset_fingerprint: str = ""
    universe_fingerprint: str = ""
    seed: Optional[int] = None
    train_end: Optional[str] = None
    valid_end: Optional[str] = None
    failure_reason: Optional[str] = None
    holdout_viewed: bool = False
    llm_model: Optional[str] = None
    prompt_hash: Optional[str] = None
    metrics: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    experiment_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExperimentRegistry:
    def __init__(self, path: str | Path = "runtime/registry.sqlite3", repo_root: str | Path | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.repo_root = repo_root
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- writing -------------------------------------------------------------
    def record(self, rec: ExperimentRecord) -> str:
        prov = git_provenance(self.repo_root)
        with self._conn() as c:
            c.execute(
                """INSERT INTO experiments
                (experiment_id, parent_id, family, factor_id, expression, expression_hash,
                 generator, created_at, git_commit, git_dirty, command, config_json,
                 dataset_fingerprint, universe_fingerprint, seed, train_end, valid_end,
                 status, failure_reason, holdout_viewed, llm_model, prompt_hash,
                 metrics_json, artifacts_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rec.experiment_id, rec.parent_id, rec.family, rec.factor_id,
                    rec.expression, rec.expression_hash, rec.generator, rec.created_at,
                    prov["git_commit"], int(prov["git_dirty"]) if prov["git_dirty"] is not None else None,
                    rec.command, json.dumps(rec.config), rec.dataset_fingerprint,
                    rec.universe_fingerprint, rec.seed, rec.train_end, rec.valid_end,
                    rec.status, rec.failure_reason, int(rec.holdout_viewed),
                    rec.llm_model, rec.prompt_hash,
                    json.dumps(rec.metrics), json.dumps(rec.artifacts),
                ),
            )
        return rec.experiment_id

    def update_status(self, experiment_id: str, status: str, failure_reason: str | None = None) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE experiments SET status=?, failure_reason=? WHERE experiment_id=?",
                (status, failure_reason, experiment_id),
            )

    # -- reading -------------------------------------------------------------
    def get(self, experiment_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        return dict(row) if row else None

    def list(self, family: str | None = None, status: str | None = None) -> list[dict]:
        q = "SELECT * FROM experiments"
        clauses, params = [], []
        if family:
            clauses.append("family=?"); params.append(family)
        if status:
            clauses.append("status=?"); params.append(status)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at"
        with self._conn() as c:
            return [dict(r) for r in c.execute(q, params).fetchall()]

    def family_trial_count(self, family: str) -> int:
        """Total attempts in a search family — the trial count for DSR/FDR."""
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM experiments WHERE family=?", (family,)).fetchone()[0])

    def lineage(self, experiment_id: str) -> list[dict]:
        """Ancestor chain from root to ``experiment_id`` (inclusive)."""
        chain: list[dict] = []
        current = self.get(experiment_id)
        while current:
            chain.append(current)
            parent = current.get("parent_id")
            current = self.get(parent) if parent else None
        return list(reversed(chain))

    # -- holdout governance --------------------------------------------------
    def record_holdout_access(self, family: str, experiment_id: str | None, reason: str = "") -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO holdout_access (family, experiment_id, accessed_at, reason) VALUES (?,?,?,?)",
                (family, experiment_id, datetime.now(timezone.utc).isoformat(), reason),
            )
            if experiment_id:
                c.execute("UPDATE experiments SET holdout_viewed=1 WHERE experiment_id=?", (experiment_id,))
            return int(cur.lastrowid)

    def holdout_access_count(self, family: str) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM holdout_access WHERE family=?", (family,)).fetchone()[0])


__all__ = ["ExperimentRegistry", "ExperimentRecord", "git_provenance"]
