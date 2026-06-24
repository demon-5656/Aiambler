from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Program:
    statements: list["Statement"]


@dataclass(frozen=True)
class Statement:
    line: int


@dataclass(frozen=True)
class UseStatement(Statement):
    system: str
    mode: str


@dataclass(frozen=True)
class DryStatement(Statement):
    enabled: bool = True


@dataclass(frozen=True)
class Assignment(Statement):
    name: str
    expr: "Expression"


@dataclass(frozen=True)
class ExprStatement(Statement):
    expr: "Expression"


@dataclass(frozen=True)
class Expression:
    pass


@dataclass(frozen=True)
class VarRef(Expression):
    name: str


@dataclass(frozen=True)
class Query(Expression):
    entity: str
    params: dict[str, Any] = field(default_factory=dict)
    system: str | None = None


@dataclass(frozen=True)
class Command(Expression):
    system: str
    entity: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Transform(Expression):
    name: str
    args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Output(Expression):
    fmt: str


@dataclass(frozen=True)
class Pipeline(Expression):
    source: Expression
    steps: list[Expression]

