# Aiambler MVP

Aiambler is a compact executable intent language for AI agents.

This Python package is the reference prototype. The lightweight runtime is the
native C interpreter in `native/`. The language core is intended for small local
tasks first: arithmetic, text parsing, and file reads.

The Python reference contains:

- line-oriented parser and AST;
- interpreter with `ro`, `rw`, `admin` access modes;
- `dry` previews for mutating actions;
- pipeline transforms: `group`, `sum`/`summarize`, `filter`, `sort`, `limit`, `has`;
- outputs: `out.md`, `out.json`, `out.table`, `out.text`;
- mock `b24` and `gm` connectors;
- structured action logs;
- Python compiler.

## Examples

```aiambler
use b24 ro
t = task? resp:15 status:open
t |> group(project) |> sum(title,deadline,status,risk) |> out.md
```

```aiambler
use b24 rw
dry
b24.task.update id:123 stage:3199
```

## CLI

Install the package in editable mode during development:

```bash
cd /home/pc243/GIT/Aiambler
python -m venv .venv
.venv/bin/python -m pip install -e .
```

Run an Aiambler script file:

```bash
.venv/bin/aiambler script.ai
python -m aiambler script.ai
.venv/bin/aiambler --compile-python script.ai
.venv/bin/aiambler --logs script.ai
```

Example `script.ai`:

```aiambler
use b24 ro
t = task? resp:15 status:open
t |> group(project) |> sum(title,deadline,status,risk) |> out.md
```
