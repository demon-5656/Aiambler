# Aiambler MVP

Aiambler is a token-min execution language for LLM agents.

The model should reason in natural language and emit a compact executable plan;
Aiambler should perform exact text parsing, numeric extraction, aggregation, and
IO in a small native runtime.

The goal is not to replace Python for applications. The goal is to avoid Python
boilerplate, virtual environments, and hallucinated arithmetic for common
agent-side tasks.

See:

- [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md) for product intent;
- [docs/PRIMITIVES.md](docs/PRIMITIVES.md) for primitive coverage;
- [docs/GOLDEN_TASKS.md](docs/GOLDEN_TASKS.md) for verified agent tasks;
- [docs/ROADMAP.md](docs/ROADMAP.md) for the release roadmap.

This repository contains a v0.1 MVP implementation focused on small local tasks:

- arithmetic expressions;
- variables;
- file reads;
- text filters;
- number extraction and aggregation;
- tiny pipe chains;
- optional mock connector experiments.

## Roadmap Snapshot

Aiambler is moving toward a stable LLM execution layer in small releases:

| Version | Focus | Status |
| --- | --- | --- |
| `v0.2` | Verified token-min core, golden tasks, docs, token benchmarks | active |
| `v0.3` | Strict IR normalization, better errors, dimension visibility | next |
| `v0.4` | Comparisons, regex, JSON, dates, min/max, grouped reducers | planned |
| `v0.5` | Parallel scheduler for independent same-dimension tasks | planned |
| `v0.6` | Safe HTTP/shell/connectors and MCP wrapper | planned |
| `v1.0` | Stable spec, packaged runtime, release-gated benchmarks | target |

Near-term priorities:

1. Keep all readable, compact, and token-min forms normalizing into one IR.
2. Add negative tests and precise diagnostics for generated scripts.
3. Implement comparison and regex filters before full control flow.
4. Add JSON/date primitives for common agent workflows.
5. Expose the native runtime as an MCP tool.

## When To Use Aiambler

Use Aiambler when an LLM needs exact local computation around its reasoning:

- parse logs or plain text;
- filter rows;
- extract numbers;
- aggregate values;
- transform small files;
- write a report or console result;
- verify a numeric answer instead of estimating it from model weights.

Do not use Aiambler as a full application language. For complex applications,
large libraries, UI frameworks, or long-lived business systems, generate normal
code in a general-purpose language. Aiambler is the small deterministic
calculator/parser beside the model, not the whole software stack.

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
- compact pipes: `?`, `#`, `##`, `+`, `+/`, `@N`, `@tN`, `~>old=new`, `!`
- pipes: `grep(...)`, `nums`, `sum`, `count`, `len`, `out`
- verbose aliases: `filter(...)`, `extract_numbers`, `average`, `pick(...)`,
  `take(...)`, `replace(old,new)`, `output`
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
<prices.tsv|@t2|#|+|!
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
For one-shot scans, direct `<file|...` pipelines are the preferred token-minimal
form because they avoid a temporary variable and a second line.

Inspect compact IR and execution plan:

```bash
build/aiambler --dump-ir --dump-plan examples/compact.ai
```

`--dump-plan` also prints operation metadata such as `SOURCE`, `MAP`,
`REDUCE`, `SINK`, and `ORDERED`.
Direct verbose read pipelines also normalize into IR and can use the same
planned scan/reduce backend.
Token-min candidates for units, loops, objects, and dimensional namespaces are
tracked in [docs/TOKEN_MIN.md](docs/TOKEN_MIN.md) and
[docs/DIMENSIONS.md](docs/DIMENSIONS.md).
The native runtime already supports dimension-prefixed line ordering (`3 `,
`2 `, `1 `, `0 `, colon variants such as `3:`, and
`source`/`matrix`/`log`/`system`). Repeated writes to the same name inside one
dimension keep the value from the earlier source line.
The `!>path` sink writes the current value to a file for system-output steps;
`.path` is the shorter pipeline sink form, and `name.path` is the shortest
suffix form for writing a simple variable.
For token-min generated code, a bare `3 <file` stores an implicit source and
lower dimensions can use fused compact pipelines such as `2 x=?needle@2#+`.
Parallel execution and strict per-dimension variable visibility are still
tracked as follow-up work.

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

Golden agent tasks:

```bash
make bench-golden
```

This runs ordinary LLM-agent tasks where Aiambler performs exact parsing,
aggregation, and IO, then verifies output against Python and AWK baselines.

Current local result with `tiktoken:cl100k_base`:

```text
task              ai_tok py_tok awk_tok ai_ms  py_ms  awk_ms
log_error_sum         20     57      44  1.05  13.58    1.12
csv_split_outputs     44     87      46  0.97   9.77    1.09
price_average         21     63      49  1.02  13.69    1.13
config_replace        23     28      16  1.00   7.80    1.06
```

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
python3 benchmarks/token_count.py --tiktoken --encoding cl100k_base
```

Current token-count result with `tiktoken:cl100k_base`:

```text
task        compact verbose token_min best best_form python awk  py/best awk/best
logs             16      19        16   16 compact       56  51     3.50     3.19
finance          23      28        23   23 compact       60  31     2.61     1.35
prices_avg       17      20        17   17 compact       62  63     3.65     3.71
replace          22      23        22   22 compact       27  23     1.23     1.05
composite        16      19        16   16 compact       56  51     3.50     3.19
```

Compact syntax is not assumed to be token-optimal. The benchmark compares both
compact and verbose Aiambler forms, tracks a `token_min` profile for model
generation, and reports the cheaper active form as `best`.

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
