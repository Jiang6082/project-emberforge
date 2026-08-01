"""Mutation generator: change exactly one horizon literal in an expression.

Single-step mutations keep lineage interpretable — each child differs from its
parent by one operator/horizon/input, so a family view reads as an edit history.
"""

from __future__ import annotations

from ..dsl.nodes import Call, Const, Node
from ..dsl.spec import FactorSpec, make_factor


def _replace_first_window(node: Node, new_value: int, _state: dict) -> Node:
    from ..dsl import operators

    if isinstance(node, Call):
        spec = operators.REGISTRY.get(node.op)
        args = list(node.args)
        if spec is not None and spec.window_args and not _state["done"]:
            idx = spec.window_args[0]
            if isinstance(args[idx], Const):
                args[idx] = Const(float(new_value))
                _state["done"] = True
                return Call(node.op, tuple(args))
        args = [_replace_first_window(a, new_value, _state) for a in args]
        return Call(node.op, tuple(args))
    return node


def mutate_horizon(parent: FactorSpec, new_window: int, suffix: str | None = None) -> FactorSpec | None:
    """Return a child with its first window literal set to ``new_window``."""
    from ..dsl.canonical import to_string

    state = {"done": False}
    tree = _replace_first_window(parent.tree(), new_window, state)
    if not state["done"]:
        return None
    new_expr = to_string(tree)
    child_id = f"{parent.factor_id}_m{suffix or new_window}"
    try:
        return make_factor(
            factor_id=child_id,
            expression=new_expr,
            description=f"mutation of {parent.factor_id}: window -> {new_window}",
            economic_hypothesis=parent.economic_hypothesis,
            expected_sign=parent.expected_sign,
            generator="mutation",
            parent_ids=(parent.factor_id,),
        )
    except Exception:
        return None


def mutate_family(parent: FactorSpec, windows=(5, 10, 20, 60)) -> list[FactorSpec]:
    out = []
    for w in windows:
        child = mutate_horizon(parent, w)
        if child and child.expression_hash != parent.expression_hash:
            out.append(child)
    return out
