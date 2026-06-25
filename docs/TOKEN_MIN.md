# Token-Min Syntax Notes

Aiambler keeps three syntax profiles:

- verbose: readable aliases for model bootstrapping and debugging;
- compact: stable symbolic syntax for normal generated scripts;
- token_min: measured forms selected for a target tokenizer.

Token-min decisions must be benchmarked with `tiktoken`, not inferred from
character count.

## Candidate Unit Syntax

The current best measured low-level unit form for `cl100k_base` is positional:

```aiambler
$gs=<0|?1|#|+|!
```

Meaning:

- `$gs` defines a reusable unit named `gs`;
- `0`, `1`, ... are positional arguments;
- the right side is a normal pipeline template.

Readable alternative:

```aiambler
gs(p,n)=<p|?n|#|+|!
```

The readable form is slightly more expensive but easier for models to infer
without examples. The token-min profile should prefer `$name=<0|...` only after
the benchmark confirms it wins for the active tokenizer.

## Candidate Object Syntax

The currently competitive object shapes are:

```aiambler
obj task{id,title,status}
o task{id,title,status}
task:{id,title,status}
```

All are close in `cl100k_base`; object syntax should therefore be chosen for
parser simplicity and model reliability, not only raw token count.

## Candidate Loop Syntax

Measured candidates:

```aiambler
for x in rows { x|#|+ }
loop rows x|#|+
*rows|#|+
rows:*#/+
```

The shortest forms are also the least self-describing. Before implementing
loops, benchmark them on real multi-step tasks and verify that they can compile
to explicit IR ops instead of becoming ad-hoc evaluator behavior.

## Candidate Dimensional Namespace Syntax

Dimensional namespaces are tracked in [DIMENSIONS.md](DIMENSIONS.md). Current
best measured emitted form for `cl100k_base` uses numeric-space prefixes:

```aiambler
3 $src=<file
2 $m=<3|@2|#
1 $log=<2|+|!
0 $out=<1|!
```

`0:`/`1:`/`2:`/`3:` remain valid, but are often more expensive because the colon
is a separate token. Block forms such as `0:\n...` only win when many lines
share one dimension and variable names are not already short.

Readable word prefixes are useful in prompts:

```aiambler
source $src=<file
matrix $m=<source|@2|#
log $log=<matrix|+|!
system $out=<log|!
```

Single dimensional unit:

```aiambler
2:$mx=<0|?1|@2|#|+|!
```

Readable single unit:

```aiambler
matrix $mx=<0|?1|@2|#|+|!
```

The key semantic rule is downward data flow: code in dimension `n` can read
dimensions `n..max`, but higher dimensions cannot read lower ones. `3D` can
produce source cycles, `2D` can calculate over them, `1D` can log/report, and
`0D` can perform final system/device output.

## Built-In Common Sinks

Common terminal/system actions should be one short pipeline step instead of
requiring extra log variables:

```aiambler
0 err!
0 warn.warn_report.txt
```

`!` is console output. `.path` after a simple name is the shortest file output
sink; `|.path` and `!>path` remain as explicit pipeline forms.

## Fused Pipelines And Implicit Source

For generated token-min code, a `3D` bare read stores the implicit source:

```aiambler
3 <events.csv
```

Lower dimensions can then start directly with compact operators:

```aiambler
2 w=?warn@2#+
2 e=?err@2#+
```

This is equivalent to:

```aiambler
2 w=src|?warn|@2|#|+
2 e=src|?err|@2|#|+
```

The fused form is tokenizer-dependent but currently cheaper for `cl100k_base`.

## Benchmark

Run:

```bash
python3 benchmarks/syntax_tokens.py --tiktoken --encoding cl100k_base
```

Use this benchmark before adding new syntax to the runtime.
