from __future__ import annotations

import re
import shlex
from typing import Any

from .ast import (
    Assignment,
    Command,
    DryStatement,
    ExprStatement,
    Expression,
    Output,
    Pipeline,
    Program,
    Query,
    Transform,
    UseStatement,
    VarRef,
)
from .errors import ParseError


SYSTEM_ALIASES = {
    "b24": "b24",
    "bitrix": "b24",
    "bitrix24": "b24",
    "gm": "gm",
    "gmail": "gm",
    "sql": "sql",
    "file": "file",
    "shell": "shell",
}


class AiamblerParser:
    """Line-oriented parser for the v0.1 Aiambler MVP syntax."""

    _assign_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$")
    _query_re = re.compile(r"^(?:(?P<system>[A-Za-z][\w-]*)\.)?(?P<entity>[A-Za-z][\w-]*)\?(?P<params>.*)$")
    _command_re = re.compile(
        r"^(?P<system>[A-Za-z][\w-]*)\.(?P<entity>[A-Za-z][\w-]*)(?:\.(?P<action>[A-Za-z][\w-]*)|(?P<plus>\+))(?P<params>.*)$"
    )
    _output_re = re.compile(r"^out\.(?P<fmt>[A-Za-z][\w-]*)$")
    _transform_re = re.compile(r"^(?P<name>[A-Za-z][\w-]*)\((?P<args>.*)\)$")
    _var_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def parse(self, script: str) -> Program:
        statements = []
        for line_no, raw in enumerate(script.splitlines(), start=1):
            line = self._strip_comment(raw).strip()
            if not line:
                continue
            if line.startswith("use "):
                statements.append(self._parse_use(line, line_no))
                continue
            if line == "dry":
                statements.append(DryStatement(line=line_no))
                continue
            assign = self._assign_re.match(line)
            if assign:
                statements.append(
                    Assignment(line=line_no, name=assign.group(1), expr=self._parse_expr(assign.group(2), line_no))
                )
                continue
            statements.append(ExprStatement(line=line_no, expr=self._parse_expr(line, line_no)))
        return Program(statements=statements)

    def _parse_use(self, line: str, line_no: int) -> UseStatement:
        parts = line.split()
        if len(parts) != 3:
            raise ParseError("use statement must be: use <system> <ro|rw|admin>", line=line_no, cmd=line)
        system = SYSTEM_ALIASES.get(parts[1], parts[1])
        mode = parts[2]
        if mode not in {"ro", "rw", "admin"}:
            raise ParseError("unknown access mode", line=line_no, mode=mode)
        return UseStatement(line=line_no, system=system, mode=mode)

    def _parse_expr(self, text: str, line_no: int) -> Expression:
        parts = [part.strip() for part in text.split("|>")]
        if any(not part for part in parts):
            raise ParseError("empty pipeline segment", line=line_no, cmd=text)
        source = self._parse_atom(parts[0], line_no)
        if len(parts) == 1:
            return source
        return Pipeline(source=source, steps=[self._parse_atom(part, line_no) for part in parts[1:]])

    def _parse_atom(self, text: str, line_no: int) -> Expression:
        output = self._output_re.match(text)
        if output:
            return Output(fmt=output.group("fmt"))

        query = self._query_re.match(text)
        if query:
            system = query.group("system")
            return Query(
                system=SYSTEM_ALIASES.get(system, system) if system else None,
                entity=query.group("entity"),
                params=self._parse_params(query.group("params"), line_no),
            )

        command = self._command_re.match(text)
        if command:
            action = "create" if command.group("plus") else command.group("action")
            return Command(
                system=SYSTEM_ALIASES.get(command.group("system"), command.group("system")),
                entity=command.group("entity"),
                action=action,
                params=self._parse_params(command.group("params"), line_no),
            )

        transform = self._transform_re.match(text)
        if transform:
            args = [arg.strip() for arg in transform.group("args").split(",") if arg.strip()]
            return Transform(name=transform.group("name"), args=args)

        if self._var_re.match(text):
            return VarRef(name=text)

        raise ParseError("cannot parse expression", line=line_no, cmd=text)

    def _parse_params(self, text: str, line_no: int) -> dict[str, Any]:
        params: dict[str, Any] = {}
        text = text.strip()
        if not text:
            return params
        for token in shlex.split(text):
            if ":" not in token:
                raise ParseError("parameter must be key:value", line=line_no, token=token)
            key, raw_value = token.split(":", 1)
            if not key:
                raise ParseError("empty parameter key", line=line_no, token=token)
            params[key] = self._coerce_value(raw_value)
        return params

    def _coerce_value(self, value: str) -> Any:
        if value in {"true", "false"}:
            return value == "true"
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
        return value

    def _strip_comment(self, raw: str) -> str:
        in_quote = False
        quote = ""
        for idx, char in enumerate(raw):
            if char in {'"', "'"} and (idx == 0 or raw[idx - 1] != "\\"):
                if in_quote and char == quote:
                    in_quote = False
                elif not in_quote:
                    in_quote = True
                    quote = char
            if char == "#" and not in_quote:
                return raw[:idx]
        return raw

