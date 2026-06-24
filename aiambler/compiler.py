from __future__ import annotations

from typing import Any

from .ast import Assignment, Command, DryStatement, ExprStatement, Expression, Output, Pipeline, Program, Query, Transform, UseStatement, VarRef


class PythonCompiler:
    """Compile Aiambler MVP AST into readable Python-like code."""

    def compile(self, program: Program) -> str:
        lines = [
            "# Generated from Aiambler",
            "from aiambler.python_runtime import Connector, group_by, summarize, filter_rows, sort_rows, print_output",
            "",
        ]
        for statement in program.statements:
            if isinstance(statement, UseStatement):
                lines.append(f"{statement.system} = Connector({statement.system!r}, mode={statement.mode!r})")
            elif isinstance(statement, DryStatement):
                lines.append("dry_run = True")
            elif isinstance(statement, Assignment):
                lines.append(f"{statement.name} = {self._expr(statement.expr)}")
            elif isinstance(statement, ExprStatement):
                lines.append(self._expr(statement.expr))
        return "\n".join(lines) + "\n"

    def _expr(self, expr: Expression) -> str:
        if isinstance(expr, VarRef):
            return expr.name
        if isinstance(expr, Query):
            system = expr.system or self._default_system(expr.entity)
            return f"{system}.search({expr.entity!r}, {self._params(expr.params)})"
        if isinstance(expr, Command):
            return f"{expr.system}.{expr.action}({expr.entity!r}, {self._params(expr.params)})"
        if isinstance(expr, Pipeline):
            current = self._expr(expr.source)
            for step in expr.steps:
                current = self._pipe_step(current, step)
            return current
        if isinstance(expr, Output):
            return f"print_output(None, {expr.fmt!r})"
        if isinstance(expr, Transform):
            return self._pipe_step("None", expr)
        return "None"

    def _pipe_step(self, current: str, step: Expression) -> str:
        if isinstance(step, Transform):
            if step.name in {"sum", "summarize"}:
                return f"summarize({current}, {step.args!r})"
            if step.name == "group":
                return f"group_by({current}, {step.args[0]!r})"
            if step.name == "filter":
                return f"filter_rows({current}, {step.args[0]!r})"
            if step.name == "sort":
                direction = step.args[1] if len(step.args) > 1 else "asc"
                return f"sort_rows({current}, {step.args[0]!r}, {direction!r})"
            if step.name == "limit":
                return f"list({current})[:{int(step.args[0])}]"
            if step.name == "has":
                return f"[row for row in {current} if row.get({step.args[0]!r})]"
        if isinstance(step, Output):
            return f"print_output({current}, {step.fmt!r})"
        if isinstance(step, Command):
            return f"[{step.system}.{step.action}({step.entity!r}, dict({self._params(step.params)}, _input=item)) for item in {current}]"
        return current

    def _params(self, params: dict[str, Any]) -> str:
        if not params:
            return "{}"
        return "{" + ", ".join(f"{key!r}: {value!r}" for key, value in params.items()) + "}"

    def _default_system(self, entity: str) -> str:
        return {"task": "b24", "deal": "b24", "mail": "gm"}.get(entity, "connector")

