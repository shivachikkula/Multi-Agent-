"""Simple arithmetic tool — a stand-in for an 'Azure Function' connector
that does deterministic compute an LLM shouldn't be trusted to do itself.
"""
from __future__ import annotations

import ast
import operator
from typing import Any

from core.tools.base import Tool

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.Pow: operator.pow,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


class CalculatorTool(Tool):
    name = "calculate"
    description = "Evaluate a basic arithmetic expression, e.g. '1000 * 0.15 + 42'."
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    }

    async def run(self, expression: str, **_: Any) -> float:
        return _safe_eval(ast.parse(expression, mode="eval").body)
