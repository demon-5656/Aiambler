from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
from .errors import AccessDeniedError, RuntimeAiamblerError, UnknownCommandError, UnknownFieldError


RISK_BY_ACTION = {
    "search": "read",
    "get": "read",
    "read": "read",
    "create": "write",
    "update": "write",
    "send": "send",
    "delete": "delete",
    "exec": "shell",
    "bulk": "bulk",
}

ALLOWED_RISKS = {
    "ro": {"read"},
    "rw": {"read", "write", "send"},
    "admin": {"read", "write", "send", "delete", "shell", "bulk"},
}

ENTITY_SYSTEM = {
    "task": "b24",
    "deal": "b24",
    "mail": "gm",
}


@dataclass
class ActionLog:
    timestamp: str
    user: str
    agent: str
    script_id: str
    system: str
    entity: str
    action: str
    risk_level: str
    dry_run: bool
    result: str
    error: str | None = None


class AiamblerRuntime:
    def __init__(
        self,
        *,
        user: str = "local",
        agent: str = "codex",
        script_id: str = "adhoc",
        connectors: dict[str, "MockConnector"] | None = None,
    ) -> None:
        self.user = user
        self.agent = agent
        self.script_id = script_id
        self.modes: dict[str, str] = {}
        self.vars: dict[str, Any] = {}
        self.dry_run = False
        self.logs: list[ActionLog] = []
        self.connectors = connectors or {"b24": BitrixMockConnector(), "gm": GmailMockConnector()}

    def execute(self, program: Program) -> Any:
        result: Any = None
        for statement in program.statements:
            if isinstance(statement, UseStatement):
                self.modes[statement.system] = statement.mode
                self._ensure_connector(statement.system)
                result = None
            elif isinstance(statement, DryStatement):
                self.dry_run = statement.enabled
                result = None
            elif isinstance(statement, Assignment):
                result = self._eval(statement.expr, statement.line)
                self.vars[statement.name] = result
            elif isinstance(statement, ExprStatement):
                result = self._eval(statement.expr, statement.line)
            else:
                raise RuntimeAiamblerError("unsupported statement", line=statement.line)
        return result

    def logs_as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.logs]

    def _eval(self, expr: Expression, line: int) -> Any:
        if isinstance(expr, VarRef):
            if expr.name not in self.vars:
                raise RuntimeAiamblerError("unknown variable", line=line, var=expr.name)
            return self.vars[expr.name]
        if isinstance(expr, Query):
            return self._query(expr, line)
        if isinstance(expr, Command):
            return self._command(expr, line)
        if isinstance(expr, Pipeline):
            value = self._eval(expr.source, line)
            for step in expr.steps:
                value = self._apply_step(value, step, line)
            return value
        if isinstance(expr, Output):
            return self._format_output(None, expr.fmt)
        if isinstance(expr, Transform):
            return self._apply_transform(None, expr, line)
        raise RuntimeAiamblerError("unsupported expression", line=line)

    def _apply_step(self, value: Any, step: Expression, line: int) -> Any:
        if isinstance(step, Transform):
            return self._apply_transform(value, step, line)
        if isinstance(step, Output):
            return self._format_output(value, step.fmt)
        if isinstance(step, Command):
            payload = value if isinstance(value, list) else [value]
            return [self._command(step, line, item) for item in payload]
        raise RuntimeAiamblerError("unsupported pipeline step", line=line)

    def _query(self, query: Query, line: int) -> list[dict[str, Any]]:
        system = self._resolve_system(query.system, query.entity)
        self._check_access(system, "read", line, cmd=f"{system}.{query.entity}.search")
        connector = self._ensure_connector(system)
        result = connector.search(query.entity, query.params)
        self._log(system, query.entity, "search", "read", False, f"{len(result)} rows")
        return result

    def _command(self, command: Command, line: int, pipeline_item: Any | None = None) -> Any:
        risk = RISK_BY_ACTION.get(command.action, "write")
        self._check_access(command.system, risk, line, cmd=f"{command.system}.{command.entity}.{command.action}")
        connector = self._ensure_connector(command.system)
        params = dict(command.params)
        if pipeline_item is not None:
            params["_input"] = pipeline_item
        if self.dry_run and risk != "read":
            preview = connector.preview(command.entity, command.action, params, risk)
            self._log(command.system, command.entity, command.action, risk, True, "preview")
            return preview
        result = connector.execute(command.entity, command.action, params)
        self._log(command.system, command.entity, command.action, risk, False, "ok")
        return result

    def _apply_transform(self, value: Any, transform: Transform, line: int) -> Any:
        if transform.name in {"sum", "summarize"}:
            return summarize(value, transform.args)
        if transform.name == "group":
            self._require_args(transform, 1, line)
            return group_by(value, transform.args[0], line)
        if transform.name == "filter":
            self._require_args(transform, 1, line)
            return filter_rows(value, transform.args[0], line)
        if transform.name == "sort":
            self._require_args(transform, 1, line)
            direction = transform.args[1] if len(transform.args) > 1 else "asc"
            return sort_rows(value, transform.args[0], direction, line)
        if transform.name == "limit":
            self._require_args(transform, 1, line)
            return list(value or [])[: int(transform.args[0])]
        if transform.name == "has":
            self._require_args(transform, 1, line)
            return [row for row in list(value or []) if row.get(transform.args[0]) not in (None, "", [])]
        raise UnknownCommandError("unknown transform", line=line, cmd=transform.name)

    def _format_output(self, value: Any, fmt: str) -> str:
        if fmt == "json":
            return json.dumps(value, ensure_ascii=False, indent=2)
        if fmt == "md":
            return to_markdown(value)
        if fmt == "table":
            return to_table(value)
        if fmt == "text":
            return str(value)
        raise UnknownCommandError("unknown output format", cmd=f"out.{fmt}")

    def _resolve_system(self, explicit: str | None, entity: str) -> str:
        if explicit:
            return explicit
        if entity in ENTITY_SYSTEM:
            return ENTITY_SYSTEM[entity]
        for system in self.modes:
            return system
        raise RuntimeAiamblerError("cannot resolve system for entity", entity=entity)

    def _check_access(self, system: str, risk: str, line: int, *, cmd: str) -> None:
        mode = self.modes.get(system)
        if mode is None:
            raise AccessDeniedError("system is not connected with use", line=line, cmd=cmd, system=system)
        if risk not in ALLOWED_RISKS[mode]:
            raise AccessDeniedError(
                f"current mode is {mode}, but action requires higher access",
                line=line,
                cmd=cmd,
                risk=risk,
            )

    def _ensure_connector(self, system: str) -> "MockConnector":
        if system not in self.connectors:
            raise UnknownCommandError("unknown connector", system=system)
        return self.connectors[system]

    def _require_args(self, transform: Transform, count: int, line: int) -> None:
        if len(transform.args) < count:
            raise RuntimeAiamblerError("not enough transform arguments", line=line, cmd=transform.name)

    def _log(self, system: str, entity: str, action: str, risk: str, dry_run: bool, result: str, error: str | None = None) -> None:
        self.logs.append(
            ActionLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                user=self.user,
                agent=self.agent,
                script_id=self.script_id,
                system=system,
                entity=entity,
                action=action,
                risk_level=risk,
                dry_run=dry_run,
                result=result,
                error=error,
            )
        )


class MockConnector:
    def search(self, entity: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def execute(self, entity: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action not in {"create", "update", "send", "delete"}:
            raise UnknownCommandError("unknown connector action", cmd=action)
        return {"ok": True, "entity": entity, "action": action, "params": params}

    def preview(self, entity: str, action: str, params: dict[str, Any], risk: str) -> dict[str, Any]:
        return {
            "dry_run": True,
            "action": action,
            "entity": entity,
            "id": params.get("id"),
            "changes": {key: value for key, value in params.items() if key not in {"id", "_input"}},
            "risk": risk,
            "requires_confirmation": risk != "read",
        }


class BitrixMockConnector(MockConnector):
    tasks = [
        {"id": 101, "title": "Проверить гарантию", "resp": 15, "status": "open", "project": "Проект 1", "deadline": "2026-06-30", "risk": "low"},
        {"id": 102, "title": "Согласовать отгрузку", "resp": 15, "status": "open", "project": "Проект 2", "deadline": "2026-06-28", "risk": "medium"},
        {"id": 103, "title": "Закрыть архив", "resp": 11, "status": "closed", "project": "Проект 1", "deadline": "2026-05-01", "risk": "low"},
    ]
    deals = [
        {"id": 201, "title": "Ёлка городская", "stage": "production", "manager": "Дмитрий", "amount": 120000},
        {"id": 202, "title": "Арка световая", "stage": "production", "manager": "Анна", "amount": 80000},
    ]

    def search(self, entity: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        data = {"task": self.tasks, "deal": self.deals}.get(entity)
        if data is None:
            raise UnknownCommandError("unknown Bitrix entity", entity=entity)
        return match_params(data, params)


class GmailMockConnector(MockConnector):
    mails = [
        {"id": "m1", "from": "client", "body": "Нужен дедлайн до пятницы", "deadline": "2026-06-26"},
        {"id": "m2", "from": "client", "body": "Спасибо, без задач", "deadline": None},
        {"id": "m3", "from": "vendor", "body": "Счет во вложении", "deadline": None},
    ]

    def search(self, entity: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if entity != "mail":
            raise UnknownCommandError("unknown Gmail entity", entity=entity)
        return match_params(self.mails, {key: value for key, value in params.items() if key != "after"})


def match_params(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    return [row.copy() for row in rows if all(row.get(key) == value for key, value in params.items())]


def group_by(rows: Any, field: str, line: int) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in list(rows or []):
        if field not in row:
            raise UnknownFieldError("group field not found", line=line, field=field)
        grouped[str(row[field])].append(row)
    return dict(grouped)


def summarize(value: Any, fields: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: summarize(rows, fields) for key, rows in value.items()}
    rows = list(value or [])
    if not fields:
        return rows
    return [{field: row.get(field) for field in fields} for row in rows]


def filter_rows(rows: Any, expr: str, line: int) -> list[dict[str, Any]]:
    match = __import__("re").fullmatch(r"\s*([A-Za-z_][\w]*)\s*(==|!=|<=|>=|<|>)\s*(.+?)\s*", expr)
    if not match:
        raise RuntimeAiamblerError("unsupported filter expression", line=line, expr=expr)
    field, op, raw = match.groups()
    target = coerce_filter_value(raw)
    result = []
    for row in list(rows or []):
        if field not in row:
            raise UnknownFieldError("filter field not found", line=line, field=field)
        if compare(row[field], op, target):
            result.append(row)
    return result


def sort_rows(rows: Any, field: str, direction: str, line: int) -> list[dict[str, Any]]:
    rows_list = list(rows or [])
    if rows_list and field not in rows_list[0]:
        raise UnknownFieldError("sort field not found", line=line, field=field)
    return sorted(rows_list, key=lambda row: row.get(field), reverse=direction == "desc")


def coerce_filter_value(raw: str) -> Any:
    raw = raw.strip().strip('"\'')
    if raw.endswith("d") and raw[:-1].isdigit():
        return int(raw[:-1])
    if raw.isdigit():
        return int(raw)
    return raw


def compare(left: Any, op: str, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    return False


def to_markdown(value: Any) -> str:
    if isinstance(value, dict):
        lines: list[str] = []
        for key, rows in value.items():
            lines.append(f"{key}:")
            for row in rows:
                if isinstance(row, dict):
                    details = "; ".join(f"{field}: {val}" for field, val in row.items())
                    lines.append(f"- {details}")
                else:
                    lines.append(f"- {row}")
            lines.append("")
        return "\n".join(lines).strip()
    if isinstance(value, list):
        return "\n".join(f"- {row}" for row in value)
    return "" if value is None else str(value)


def to_table(value: Any) -> str:
    rows = value
    if isinstance(value, dict):
        rows = [dict({"group": group}, **row) for group, items in value.items() for row in items]
    rows = list(rows or [])
    if not rows:
        return ""
    headers = list(rows[0].keys())
    lines = [" | ".join(headers), " | ".join("---" for _ in headers)]
    for row in rows:
        lines.append(" | ".join(str(row.get(header, "")) for header in headers))
    return "\n".join(lines)

