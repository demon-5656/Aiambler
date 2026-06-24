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

Compact core syntax:

```aiambler
t<examples/numbers.txt
t|?price|#|+|!
```

See [docs/OPERATORS.md](docs/OPERATORS.md) for the compact operator table.
Compact file pipelines use a fused scan path for `?` + `#` + `+` + `!`.
That path scans the file directly and does not materialize the full text buffer.
Compact pipe chains are normalized into a small native `Op[]` IR before
execution.

Native smoke tests:

```bash
make test-native
```

## Speed Comparison

Run the local benchmark:

```bash
make native
python3 benchmarks/run.py --runs 500 --rows 100
```

On the current machine, with 500 process launches per case:

```text
case                median ms    x ai
aiambler math           0.890    1.00
python math             8.189    9.21
awk math                0.928    1.04
aiambler text           0.778    1.00
aiambler compact        0.717    0.90
python text            12.120   15.57
awk text                1.096    1.41
```

This measures full process startup plus script execution. For tiny tasks that is
the cost users feel most.

Heavy floating-point and matrix benchmarks:

```bash
python3 benchmarks/run.py --mode heavy --runs 3 --jobs 1,2,4,8,16 --fp-iters 3000000 --matrix-size 256
```

Current result on a 16-thread machine:

```text
case                median ms    vs ai-j1
aiambler-j1 fp        106.227       1.00
aiambler-j16 fp        10.029       0.09
python fp            2087.363      19.65
aiambler-j1 mm          8.880       1.00
aiambler-j16 mm         2.849       0.32
python mm            1609.822     181.29
numpy mm               56.140       6.32
```

The heavy benchmark also measures full process startup. NumPy includes Python
startup and import overhead, so this is an end-to-end command latency comparison,
not a BLAS-only microbenchmark.

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
