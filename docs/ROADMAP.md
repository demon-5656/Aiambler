# Aiambler Core Roadmap

Aiambler should become a compact runtime for AI-generated commands, not a
human-first scripting language. The native runtime is the source of truth.
Python stays as a reference implementation and test harness.

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

## Phase 3: Fusion

Fuse common pipelines:

```text
READ + GREP + NUMS + SUM => SCAN_SUM_CONTAINS
READ + NUMS + SUM        => SCAN_SUM_NUMS
```

The tiny backend runs the fused operation sequentially. The native backend splits
input into chunks and reduces local results.

## Phase 4: Parallel Runtime

- Keep `--jobs N`.
- Add operation metadata: `MAP`, `REDUCE`, `SOURCE`, `SINK`, `ORDERED`.
- Build a simple execution plan from IR.
- Parallelize map/reduce operations automatically when data size warrants it.

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
