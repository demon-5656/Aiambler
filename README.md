# Aiambler MVP

Aiambler is a compact executable intent language for AI agents.

The primary runtime is a small native interpreter written in C. The Python code
in this repository is a reference prototype and test harness, not the intended
runtime for edge devices.

This repository contains a v0.1 MVP implementation focused on small local tasks:

- arithmetic expressions;
- variables;
- file reads;
- text filters;
- number extraction and aggregation;
- tiny pipe chains;
- optional mock connector experiments.
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

- arithmetic: `+`, `-`, `*`, `/`, parentheses, numeric variables
- variables
- `file.read path`
- quoted text literals
- pipes: `grep(...)`, `nums`, `sum`, `count`, `len`, `out`
- legacy mock pipes: `group(...)`, `sum(fields)`, `has(...)`, `out.md`
- legacy mock connector examples: `task? ...`, `mail? ...`, `b24.task.update ...`

Small scripts:

```aiambler
a = 12 * 7 + 3
b = (a - 7) / 4
b |> out
```

```aiambler
text = file.read examples/numbers.txt
text |> grep(price) |> nums |> sum |> out
```

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
a = 1200 / 3 + 17
a |> out
```

```aiambler
text = file.read data.txt
text |> grep(total) |> nums |> sum |> out
```

## CLI

```bash
aiambler script.ai
python -m aiambler script.ai
aiambler --compile-python script.ai
aiambler --logs script.ai
```
