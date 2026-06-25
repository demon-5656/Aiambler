# Aiambler Core Roadmap

Aiambler should become a compact runtime for AI-generated commands, not a
human-first scripting language. The native runtime is the source of truth.

## Product Goal

Aiambler is a deterministic execution layer for LLM agents. The model should
reason in natural language, then emit short scripts for exact operations:
parsing, filtering, numeric extraction, aggregation, reporting, and guarded IO.

The project succeeds when common agent-side tasks can be solved with fewer
tokens and less startup overhead than Python, while producing verifiable results
instead of model-estimated arithmetic.

## Release Roadmap

### v0.2: Verified Token-Min Core

Status: active.

Goal: make the current primitive set reliable, documented, and measurable.

Deliverables:

- compact and verbose forms normalize into one IR path where practical;
- golden tasks verify Aiambler output against Python and AWK;
- token benchmarks use `tiktoken` and are recorded in README;
- fused scan/reduce paths cover grep, field pick, numbers, sum, average, count;
- token-min dimension forms are documented and covered by smoke tests;
- generated artifacts are removable via `make clean`.

Exit criteria:

- `make test` passes;
- `make bench-golden` passes;
- `benchmarks/syntax_tokens.py --tiktoken --encoding cl100k_base` records
  token-min candidate costs;
- README contains current benchmark results and project positioning.

### v0.3: Robust Agent Runtime

Goal: make generated scripts fail clearly and safely.

Deliverables:

- strict dimension visibility: `Dn` can read `Dn..max`, not lower dimensions;
- negative tests for unknown variables, missing implicit source, bad columns,
  invalid writes, and parse errors;
- clearer diagnostics with line, operation, and expected form;
- central normalizer from readable, compact, and token-min forms into IR;
- stable `--dump-ir` and `--dump-plan` output for all compact pipelines;
- README section for common model prompts and repair hints.

Exit criteria:

- malformed generated scripts produce actionable errors;
- dimension conflicts and visibility violations are tested;
- no token-min syntax bypasses IR normalization.

### v0.4: Better Data Primitives

Goal: cover the common tasks where LLMs currently reach for Python.

Deliverables:

- comparison filters: `?>N`, `?<N`, `?=x`, `?!=x`;
- regex filter/extract: `?~pattern` or measured alternative;
- min/max reductions;
- unique/count-by/top-N primitives;
- JSON path extraction;
- date/time parse and simple date comparisons;
- stronger CSV parsing for quoted fields.

Exit criteria:

- golden tasks include logs, CSV, JSON, dates, and grouped reductions;
- Aiambler remains smaller than Python on the golden token benchmark;
- each new primitive has compact and readable examples.

### v0.5: Parallel Dimension Scheduler

Goal: make the dimensional model operational, not only syntactic.

Deliverables:

- same-dimension independent assignments can run concurrently;
- first-write-wins remains deterministic for same-name conflicts;
- scheduler uses IR metadata: `SOURCE`, `MAP`, `REDUCE`, `SINK`, `ORDERED`;
- parallelism is automatic and controlled by `--jobs N`;
- benchmark reports speedup and overhead thresholds.

Exit criteria:

- independent `2D` reductions over the same `3D` source execute safely;
- ordered sinks in `1D`/`0D` remain deterministic;
- scheduler can be disabled for debugging.

### v0.6: Safe External Access

Goal: let agents use the outside world without turning Aiambler into an
unrestricted shell.

Deliverables:

- explicit access modes for file writes, shell, HTTP, and connectors;
- guarded `http.get`/`http.post` primitives;
- guarded shell primitive with allowlist/denylist policy;
- MCP wrapper exposing Aiambler as a tool;
- dry-run mode for write/network/system actions.

Exit criteria:

- default mode is read-only;
- write/network actions require explicit mode;
- MCP integration can execute golden tasks through the native runtime.

### v1.0: Stable LLM Execution Layer

Goal: provide a small, stable runtime that agents can rely on.

Deliverables:

- stable language spec for core primitives;
- stable IR and plan dump format;
- versioned token-min profile;
- packaged native binary;
- MCP server;
- safety documentation;
- benchmark suite used as release gate.

Exit criteria:

- no breaking syntax changes without migration notes;
- benchmark and smoke tests are part of release process;
- agents can choose readable or token-min syntax based on context budget.

## Principles

- Keep the core byte-oriented and ASCII-first.
- Prefer one-character operators over words in the runtime syntax.
- Keep verbose aliases only for debugging and migration.
- Make parallelism a runtime decision, not user-authored thread code.
- Optimize common pipelines by fusing operations into one pass.
- Keep connectors outside the core.

## Syntax Tracks

The operator table is specified in [OPERATORS.md](OPERATORS.md).

Verbose/debug syntax:

```aiambler
text = file.read prices.txt
text |> grep(price) |> nums |> sum |> out
```

Compact/core syntax:

```aiambler
t<prices.txt
t|?price|#|+|!
```

Core operator map:

```text
!  output
<  read file into variable
?  line contains filter
#  extract numbers
+  numeric sum / arithmetic plus
~  regex extract, future
@  field/column pick, future
|  pipe
=  assignment
```

## Phase 1: Compact Compatibility Layer

- Add compact syntax on top of the current interpreter.
- Keep current scripts working.
- Add smoke tests and benchmarks for compact scripts.

## Phase 2: IR

Introduce a compact intermediate representation:

```c
typedef enum {
    OP_PUSH_NUM,
    OP_PUSH_STR,
    OP_LOAD,
    OP_STORE,
    OP_READ,
    OP_GREP,
    OP_NUMS,
    OP_SUM,
    OP_COUNT,
    OP_LEN,
    OP_FP,
    OP_MM,
    OP_OUT
} OpCode;
```

Pipeline source code should compile into an `Op[]` program before execution.

Current status: compact pipe chains and direct verbose read pipelines compile
into a minimal `Program` of `Op` items before execution. Other verbose syntax
still uses the compatibility evaluator.

Debugging:

```bash
build/aiambler --dump-ir --dump-plan examples/compact.ai
```

## Phase 3: Fusion

Fuse common pipelines:

```text
READ + GREP + NUMS + SUM => SCAN_SUM_CONTAINS
READ + NUMS + SUM        => SCAN_SUM_NUMS
```

The tiny backend runs the fused operation sequentially. The native backend splits
input into chunks and reduces local results.

Current compatibility-layer fusion:

```aiambler
t<prices.txt
t|?price|#|+|!
```

Compact `<` stores a lazy file source. The `?`, `#`, `+`, `!` chain is executed
as one file scan instead of materializing the whole file and intermediate arrays.
This also avoids the fixed text buffer limit used by the verbose compatibility
path.

Current planner status: direct compact `OP_READ` pipelines matching scan/reduce
patterns execute through a specialized planned kernel instead of stepping through
each `Op`. Supported planned forms include grep/nums/sum, pick/nums/sum,
nums/sum, grep/pick/nums/sum, grep/nums/avg, pick/nums/avg,
grep/pick/nums/avg, and nums/avg with output. Planner matching is exact for the
whole compact pipeline. `OP_LOAD` pipelines still use the interpreter path
because variables may hold non-file values.

## Phase 4: Parallel Runtime

- Keep `--jobs N`.
- Add operation metadata: `MAP`, `REDUCE`, `SOURCE`, `SINK`, `ORDERED`.
- Build a simple execution plan from IR.
- Parallelize map/reduce operations automatically when data size warrants it.

Current status: `--jobs N` is used by heavy `fp()`/`mm()` kernels and by direct
planned file scan/reduce pipelines once input is large enough. The scan backend
splits the file into byte ranges, starts each worker at a line boundary, and
combines local numeric totals/counts for sum and average. Compact IR ops expose
basic metadata (`SOURCE`, `MAP`, `REDUCE`, `SINK`, `ORDERED`) in `--dump-plan`;
the next step is to use this metadata to build more general plans.

## Phase 5: Core Modules

Priority order:

1. math and reductions;
2. file and text scan;
3. CSV/TSV;
4. regex;
5. JSON;
6. SQLite;
7. guarded shell and HTTP;
8. external connectors.

## Agent Product Track

Benchmark package:

- Maintain five real agent tasks: logs, finance CSV, extraction, replace,
  composite pipeline.
- Maintain golden agent tasks for exact text parsing, numeric aggregation, and
  IO verification against Python/AWK baselines.
- Maintain multi-step tasks that combine repeated scans, field extraction,
  replacement, reductions, and multiple outputs.
- Report exact generated-code token counts via `tiktoken`.
- Compare compact Aiambler, verbose Aiambler, Python, and awk for the active
  tokenizer instead of assuming character count predicts token count.
- Maintain a separate `token_min` profile for model-facing generated scripts.
- Track candidate syntax for units, objects, loops, and parsers in
  [TOKEN_MIN.md](TOKEN_MIN.md) before implementing them.
- Track dimensional namespace rules in [DIMENSIONS.md](DIMENSIONS.md).
- Report runtime latency for Aiambler and baseline implementations.
- Keep results in README after stable runs.

Agent documentation:

- Product philosophy and boundaries in [PHILOSOPHY.md](PHILOSOPHY.md).
- Primitive coverage matrix in [PRIMITIVES.md](PRIMITIVES.md).
- Golden task set in [GOLDEN_TASKS.md](GOLDEN_TASKS.md).
- Prompt examples that generate valid compact Aiambler.
- Template library for common tasks.
- Safety guide for read/write/network/shell operations.

Integrations:

- LangChain tool wrapper.
- AutoGPT wrapper.
- MCP server exposing the native runtime.

Language expansion:

- CSV/TSV column operations: minimally implemented as compact `@N` for CSV and
  `@tN` for TSV field selection.
- Text replacement: minimally implemented as compact `~>old=new`.
- Token-min unit definitions.
- Dimensional line ordering for scalar/vector/matrix-style agent units:
  minimally implemented for `3:`/`2:`/`1:`/`0:` and
  `source`/`matrix`/`log`/`system`; strict variable visibility is pending.
- Object/record syntax.
- Conditionals.
- Minimal iteration/map.
- HTTP client as guarded module.
