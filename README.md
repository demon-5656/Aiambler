# Aiambler MVP

Aiambler is a compact executable intent language for AI agents.

The runtime is a small native interpreter written in C.

This repository contains a v0.1 MVP implementation focused on small local tasks:

- arithmetic expressions;
- variables;
- file reads;
- text filters;
- number extraction and aggregation;
- tiny pipe chains;
- optional mock connector experiments.

## Native Runtime

Build the native interpreter:

```bash
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
- compact pipes: `?`, `#`, `##`, `+`, `+/`, `@N`, `~>old=new`, `!`
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

CSV-like column extraction and text replacement:

```aiambler
<prices.csv|@2|#|+|!
<report.txt|~>TODO=DONE|!
```

See [docs/OPERATORS.md](docs/OPERATORS.md) for the compact operator table.
Compact file pipelines use a fused scan path for `?` + `#` + `+` + `!`.
That path scans the file directly and does not materialize the full text buffer.
Compact pipe chains are normalized into a small native `Op[]` IR before
execution.

Direct compact read pipelines such as `<file|?x|#|+|!`,
`<file|?x|#|+/|!`, and `<file|?x|@2|#|+|!` execute through the planned
scan/reduce kernel. Other compact file pipelines keep the lazy file source when
possible and materialize text only for operations such as `##` and `~>`.
For larger direct file scans, `--jobs N` splits the file into line-safe ranges
and reduces local numeric results in parallel.

Inspect compact IR and execution plan:

```bash
build/aiambler --dump-ir --dump-plan examples/compact.ai
```

`--dump-plan` also prints operation metadata such as `SOURCE`, `MAP`,
`REDUCE`, `SINK`, and `ORDERED`.

Native smoke tests:

```bash
make test-native
```

## Benchmarks

Build the native binary before running benchmarks:

```bash
make native
```

Small startup-heavy tasks:

```bash
python3 benchmarks/run.py --runs 300 --rows 100
```

Current local medians:

```text
aiambler math      0.886 ms
python math        8.151 ms
awk math           0.937 ms
aiambler text      0.787 ms
aiambler compact   0.823 ms
python text       11.993 ms
awk text           1.052 ms
```

Heavy numeric tasks:

```bash
python3 benchmarks/run.py --mode heavy --runs 3 --jobs 1,2,4,8,16 --fp-iters 3000000 --matrix-size 256
```

Current local medians:

```text
aiambler-j1 fp     90.860 ms
aiambler-j16 fp     9.764 ms
python fp        2058.109 ms
aiambler-j1 mm      8.758 ms
aiambler-j16 mm     2.805 ms
python mm        1556.135 ms
numpy mm           56.418 ms
```

Agent workload benchmark:

```bash
python3 benchmarks/agent_tasks.py --runs 30
```

Current local latency is about `1.0-1.2 ms` for the native runtime across the
five bundled agent tasks.

Multi-step workload benchmark:

```bash
python3 benchmarks/multistep_tasks.py --runs 10 --tiktoken
```

Current local result with `tiktoken:o200k_base`:

```text
task              ai_tok py_tok awk_tok ai_ms  py_ms  awk_ms
incident_triage       43    149     162  1.16  14.92    1.85
regional_sales        52    109      86  1.11  10.54    1.37
catalog_migration     42    100      79  1.21  10.19    1.28
support_digest        51    115      97  0.95   9.26    1.25
```

Token-only benchmark:

```bash
python3 benchmarks/token_count.py --tiktoken
```

Current token-count result with `tiktoken:o200k_base`:

```text
task        ai_chars ai_tok py_chars py_tok awk_chars awk_tok py/ai awk/ai
logs              50     20      169     56       124      51  2.80   2.55
finance           61     27      204     60        85      31  2.22   1.15
prices_avg        51     21      199     62       145      65  2.95   3.10
replace           61     25       96     27        77      24  1.08   0.96
composite         49     20      168     56       123      51  2.80   2.55
```

Remove generated local artifacts:

```bash
make clean
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
build/aiambler script.ai
build/aiambler --dump-ir --dump-plan script.ai
build/aiambler --jobs 4 script.ai
```
