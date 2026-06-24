"""Small helpers referenced by generated Python code."""

import json

from .runtime import (
    BitrixMockConnector,
    GmailMockConnector,
    filter_rows as runtime_filter_rows,
    group_by as runtime_group_by,
    sort_rows as runtime_sort_rows,
    summarize,
    to_markdown,
    to_table,
)


class Connector:
    def __init__(self, system: str, mode: str = "ro") -> None:
        self.system = system
        self.mode = mode
        self.impl = BitrixMockConnector() if system == "b24" else GmailMockConnector()

    def search(self, entity: str, params: dict) -> list[dict]:
        return self.impl.search(entity, params)

    def create(self, entity: str, params: dict) -> dict:
        return self.impl.execute(entity, "create", params)

    def update(self, entity: str, params: dict) -> dict:
        return self.impl.execute(entity, "update", params)


def group_by(rows, field: str):
    return runtime_group_by(rows, field, line=0)


def filter_rows(rows, expr: str):
    return runtime_filter_rows(rows, expr, line=0)


def sort_rows(rows, field: str, direction: str = "asc"):
    return runtime_sort_rows(rows, field, direction, line=0)


def print_output(value, fmt: str):
    if fmt == "md":
        return to_markdown(value)
    if fmt == "table":
        return to_table(value)
    if fmt == "json":
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)
