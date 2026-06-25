# Dimensional Namespace Model

Aiambler can model agent work as ordered dimensional spaces:

- `3D+`: source cycles, file-reading loops, batches, time windows, nested input
  collections;
- `2D`: tables, matrices, grouped row sets, aggregations and calculations over
  higher-dimensional data;
- `1D`: logs, event/output records, linear reports;
- `0D`: system effects, base outputs, devices, final sinks.

Execution is ordered by dimension:

```text
3D+ -> 2D -> 1D -> 0D
```

Each dimension has one namespace. A lower dimension can read higher dimensions,
but higher dimensions cannot read lower dimensions.

```text
read from Dn: Dn, Dn+1, ...
write from Dn: Dn only
```

This gives a simple dependency rule: data flows downward toward system effects.
Within one dimension, lines are intended to be independent tasks. The compiler
can evaluate them in parallel when their inputs are already available. Textual
order inside the same dimension is only the deterministic conflict rule: if two
tasks in the same dimension write the same name, the earlier line wins.

## Token-Min Candidate

The current shortest measured candidates for dimensional blocks are tied:

```aiambler
3 $src=<file
2 $m=<3|@2|#
1 $log=<2|+|!
0 $out=<1|!
```

Numeric-space prefixes are the token-min form for emitted code. Colon prefixes
remain valid and readable:

```aiambler
3:$src=<file
2:$m=<3|@2|#
1:$log=<2|+|!
0:$out=<1|!
```

Readable word prefixes are useful in prompts:

```aiambler
source $src=<file
matrix $m=<source|@2|#
log $log=<matrix|+|!
system $out=<log|!
```

For a single unit in a dimension:

```aiambler
2:$mx=<0|?1|@2|#|+|!
```

Meaning:

- `2:` declares that the unit lives in dimension 2;
- `$mx` is a unit name;
- `0`, `1`, ... inside the template are positional unit arguments;
- names resolved from the body search `D2`, then higher dimensions such as `D3`.

Readable form:

```aiambler
matrix $mx=<0|?1|@2|#|+|!
```

For `cl100k_base`, `2:$mx=...` and `matrix $mx=...` currently have the same
token count. Prefer the readable form in prompts and the numeric form in emitted
token-min code when both remain tied.

## Namespace Rules

1. Dimensions execute from highest to lowest.
2. Tasks inside one dimension may execute in parallel.
3. A name lookup in dimension `n` searches `n` upward to available higher
   dimensions.
4. Assignment writes into the current dimension.
5. If two assignments in the same dimension write the same name, the earlier
   source line has priority.
6. Shadowing is allowed only downward: `D1.x` may shadow `D2.x`, but `D2`
   cannot see or mutate `D1.x`.
7. Unit calls evaluate in the caller dimension unless explicitly declared with a
   dimension prefix.

## Runtime Status

The native runtime currently implements the first layer:

- numeric-space prefixes: `3 `, `2 `, `1 `, `0 `;
- numeric-colon prefixes: `3:`, `2:`, `1:`, `0:`;
- readable prefixes: `source`, `matrix`, `log`, `system`;
- dimension-prefixed lines execute from the highest dimension to the lowest,
  regardless of their textual order;
- repeated writes to the same variable in the same dimension keep the value from
  the earlier source line;
- `!>path` writes the current value to a file, `|.path` is the compact pipeline
  file sink, and `name.path` is the token-min suffix form for simple `0D`
  outputs;
- a bare `3 <path` stores an implicit source for lower-dimensional fused
  pipelines such as `2 x=?needle@2#+`;
- non-prefixed setup lines run before dimension blocks.

Parallel execution and strict per-dimension variable visibility are still
compiler/runtime tasks. Until that lands, variables are stored in the existing
shared runtime table.

## Why This Shape

This model covers common neural-agent tasks:

- read files and run source cycles in `3D+`;
- aggregate tables/matrices in `2D`;
- write logs and linear reports in `1D`;
- send final output to devices/system sinks in `0D`.

It also keeps the compiler simple: dimensions become ordered IR groups with a
strict name-resolution rule.
