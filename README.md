# Aiambler MVP

Aiambler is a compact executable intent language for AI agents.

The primary runtime is a small native interpreter written in C. The Python code
in this repository is a reference prototype and test harness, not the intended
runtime for edge devices.

This repository contains a v0.1 MVP implementation:

- line-oriented parser and AST;
- interpreter with `ro`, `rw`, `admin` access modes;
- `dry` previews for mutating actions;
- pipeline transforms: `group`, `sum`/`summarize`, `filter`, `sort`, `limit`, `has`;
- outputs: `out.md`, `out.json`, `out.table`, `out.text`;
- mock `b24` and `gm` connectors;
- structured action logs;
- Python compiler/reference runtime.

## Native Runtime

Build the native interpreter:

```bash
cd /home/pc243/GIT/Aiambler
make native
```

Run an `.ai` script:

```bash
build/aiambler examples/script.ai
```

The current native MVP has no third-party dependencies and builds into one small
binary. It supports:

- `use b24 ro|rw|admin`
- `use gm ro|rw|admin`
- `dry`
- variables
- `task? ...` and `mail? ...` mock queries
- pipes: `group(...)`, `sum(...)`, `has(...)`, `out.md`
- `b24.task.update ...`
- `b24.task+` in a pipeline
- `ro` write blocking and dry-run previews

Native smoke tests:

```bash
make test-native
```

## Python Reference

Use a virtual environment only if you need the Python prototype:

```bash
cd /home/pc243/GIT/Aiambler
python -m venv .venv
.venv/bin/python -m pip install -e .
```

After installation, run `.ai` files with the console command:

```bash
.venv/bin/aiambler examples/script.ai
```

You can also run without installing the console script while developing:

```bash
python -m aiambler examples/script.ai
```

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

```bash
aiambler script.ai
python -m aiambler script.ai
aiambler --compile-python script.ai
aiambler --logs script.ai
```
