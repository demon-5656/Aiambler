# Aiambler MVP

Aiambler is a compact executable intent language for AI agents.

The runtime is a small native interpreter written in C. The repository no longer
ships a Python implementation of the language; Python is used only for benchmark
and evaluation helper scripts.

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

Agent workload benchmark:

```bash
python3 benchmarks/agent_tasks.py --runs 50
```

This benchmark compares five common agent tasks: log analysis, CSV finance
aggregation, price extraction, text replacement, and a composite grep/nums/sum
pipeline. It reports approximate code tokens as `chars / 4` plus median command
latency for Aiambler, Python, and awk.

Current local result with 20 runs:

```text
task          ai_tok py_tok awk_tok ai_ms py_ms  awk_ms ai_vs_py_tok
logs              12     42      31  1.02 14.03   1.44        3.50
finance           15     51      21  1.12 11.20   1.54        3.40
prices_avg        13     50      36  0.96 13.82   2.41        3.85
replace           15     24      19  1.23  8.69   1.16        1.60
composite         12     42      31  1.05 12.42   1.27        3.50
```

Token-only benchmark:

```bash
python3 benchmarks/token_count.py
# optional exact tokenizer when installed:
python3 benchmarks/token_count.py --tiktoken
```

Ollama generation test:

```bash
ollama serve
python3 benchmarks/ollama_eval.py --model qwen2.5-coder:14b --task logs --targets ai --run-ai
```

The Ollama test measures model-side prompt/output token counts reported by
Ollama and can optionally execute generated Aiambler to validate it.

Known local smoke result:

```text
model=qwen2.5-coder:14b
logs ai prompt_tok=138 out_tok=20 chars=49 run:0:101307
```

Small models can fail the format-following test. For example,
`deepseek-coder:1.3b` tended to produce Python prose instead of Aiambler compact
code, which is useful as a negative benchmark for prompt robustness.

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
