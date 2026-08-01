"""Canonicalization, deterministic serialization, and hashing.

Two factor expressions that are algebraically identical up to argument order of
commutative operators must produce the *same* canonical string and therefore the
same hash. This is the first (syntactic) layer of deduplication.
"""

from __future__ import annotations

import hashlib

from . import operators
from .nodes import Call, Const, Field, Node


def _fmt_const(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)


def canonicalize(node: Node) -> Node:
    """Return a structurally-normalized copy of ``node``.

    Commutative operators get their arguments sorted by canonical string so that
    ``add(a, b)`` and ``add(b, a)`` normalize identically.
    """
    if isinstance(node, (Field, Const)):
        return node
    assert isinstance(node, Call)
    args = tuple(canonicalize(a) for a in node.args)
    spec = operators.REGISTRY.get(node.op)
    if spec is not None and spec.commutative:
        args = tuple(sorted(args, key=to_string))
    return Call(node.op, args)


def to_string(node: Node) -> str:
    """Deterministic textual serialization of a (canonical) tree."""
    if isinstance(node, Field):
        return node.name
    if isinstance(node, Const):
        return _fmt_const(node.value)
    assert isinstance(node, Call)
    inner = ",".join(to_string(a) for a in node.args)
    return f"{node.op}({inner})"


def canonical_string(node: Node) -> str:
    return to_string(canonicalize(node))


def factor_hash(node: Node) -> str:
    """Stable SHA-256 (first 16 bytes, hex) of the canonical expression."""
    digest = hashlib.sha256(canonical_string(node).encode("utf-8")).hexdigest()
    return digest[:32]
