"""Demo tools that can raise stack traces / compile() SyntaxErrors."""

from __future__ import annotations

import ast
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[Any] | Any]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition] | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools or default_tools():
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def require(self, name: str) -> ToolDefinition:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def schemas_for_prompt(self) -> str:
        chunks: list[str] = []
        for tool in self.list_tools():
            chunks.append(
                f"- {tool.name}: {tool.description}\n"
                f"  parameters: {json.dumps(tool.parameters)}"
            )
        return "\n".join(chunks)


async def _compile_python(args: dict[str, Any]) -> dict[str, Any]:
    """
    Use Python's compile() API — SyntaxError carries lineno/offset like a compiler.

    Broken snippets raise; healed snippets return the evaluated result of a
    simple assignment / expression form.
    """
    source = args.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")

    mode = args.get("mode", "exec")
    if mode not in {"exec", "eval", "single"}:
        raise ValueError("mode must be exec, eval, or single")

    # Raises SyntaxError with lineno/offset on bad input — this is the "compiler API"
    code = compile(source, filename="<agent-snippet>", mode=mode)

    if mode == "eval":
        value = eval(code, {"__builtins__": {}}, {})  # noqa: S307 — sandbox-ish demo
        return {"ok": True, "value": value, "mode": mode}

    namespace: dict[str, Any] = {"__builtins__": {}}
    exec(code, namespace, namespace)  # noqa: S102 — intentional demo surface
    # Prefer an explicit `result` binding when present
    if "result" in namespace:
        return {"ok": True, "value": namespace["result"], "mode": mode}
    return {"ok": True, "value": None, "mode": mode}


async def _eval_math(args: dict[str, Any]) -> dict[str, Any]:
    expression = args.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be a non-empty string")

    # Only allow literal arithmetic AST nodes — still raises ZeroDivisionError etc.
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Constant,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.FloorDiv,
                ast.Mod,
                ast.Pow,
                ast.USub,
                ast.UAdd,
            ),
        ):
            raise ValueError(f"disallowed AST node: {type(node).__name__}")

    value = eval(compile(tree, "<math>", "eval"), {"__builtins__": {}}, {})  # noqa: S307
    return {"ok": True, "value": value}


async def _lookup_path(args: dict[str, Any]) -> dict[str, Any]:
    payload = args.get("payload")
    path = args.get("path")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty dotted string")

    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            raise TypeError(f"cannot traverse into {type(current).__name__} at '{part}'")
        if part not in current:
            raise KeyError(part)
        current = current[part]
    return {"ok": True, "value": current}


def default_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="compile_python",
            description=(
                "Compile (and optionally exec/eval) a Python source snippet via "
                "the compile() API. Returns {ok, value, mode}."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "mode": {"type": "string", "enum": ["exec", "eval", "single"]},
                },
                "required": ["source"],
            },
            handler=_compile_python,
        ),
        ToolDefinition(
            name="eval_math",
            description="Evaluate a pure arithmetic expression. Returns {ok, value}.",
            parameters={
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
            handler=_eval_math,
        ),
        ToolDefinition(
            name="lookup_path",
            description="Look up a dotted path inside a JSON-like payload dict.",
            parameters={
                "type": "object",
                "properties": {
                    "payload": {"type": "object"},
                    "path": {"type": "string"},
                },
                "required": ["payload", "path"],
            },
            handler=_lookup_path,
        ),
    ]
