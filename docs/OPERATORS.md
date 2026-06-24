# Aiambler Operator Table

This document defines the compact operator surface for the native core. The goal
is to make scripts cheap for models to generate and cheap for runtimes to parse.

## Lexer Rule

Aiambler uses longest-match operator tokenization with a maximum operator length
of 3 bytes.

```text
try 3-byte operator
else try 2-byte operator
else try 1-byte operator
else parse literal / identifier
```

A one-byte operator is emitted only when the following byte does not form a known
two-byte or three-byte operator. This makes base symbols stable while still
allowing families such as `?`, `?>`, `?~`.

Examples:

```text
?price   => OP_HAS("price")
?>10     => OP_FILTER_GT(10)
?~rx     => OP_REGEX(rx)
```

Comments are recognized only when `#` starts a line or follows whitespace:

```text
# comment
x # comment
x|#|+|!  # # is OP_NUMS here
```

## Operator Families

Each base operator owns a family. The one-byte operator is the most common
operation. Two-byte and three-byte operators specialize it.

| Base | Family | Base Meaning | 2-Byte Layer | 3-Byte Layer |
|---|---|---|---|---|
| `!` | output/control | output current value | `!!` debug dump, `!?` assert/truthy | `!>` write output to path |
| `<` | input/read | read file/path | `<$` env read, `<@` arg read, `<~` glob read | `<http` reserved via alias, not core |
| `>` | write/export | write file | `>>` append, `>|` overwrite pipe sink | `>!` force write |
| `?` | select/filter | contains/grep | `?>`, `?<`, `?=`, `?!`, `?~` regex | `?>=`, `?<=`, `?!=` |
| `#` | number/extract | extract numbers | `##` count, `#@` index/range | `#i32`, `#f64` typed parse |
| `+` | add/reduce | sum/add | `++` increment/count rows, `+=` add assign | `+//` parallel sum hint |
| `-` | subtract/drop | subtract | `--` decrement/drop empty, `-=` subtract assign | `-//` parallel subtract reserved |
| `*` | multiply/map | multiply/product | `**` power, `*=` multiply assign, `*&` parallel map | `*mm` matrix multiply alias |
| `/` | divide/split | divide | `//` chunk/partition, `/=` divide assign | `//k` chunk size suffix |
| `%` | modulo/sample | modulo | `%%` percentage, `%?` sample/filter | reserved |
| `=` | bind/compare | assignment | `==` equality | `===` strict byte equality |
| `|` | pipe | pipe | `||` fallback/or, `|&` parallel pipe | `|&N` parallel limit suffix |
| `&` | parallel/and | and / parallel hint | `&&` logical and, `&>` async send | `&N` worker count suffix |
| `:` | split/field | split text | `::` namespace/key path, `:=` define macro | reserved |
| `;` | end/join | statement end / join | `;;` flush/end block | reserved |
| `@` | pick/address | pick field/column | `@@` all fields, `@?` field exists | `@csv` reserved alias |
| `~` | pattern | regex/match | `~>` replace, `~=` regex equality | reserved |
| `.` | path/member | member/path | `..` parent/range | `...` spread/rest |
| `,` | list | separator/list build | `,,` concat | reserved |
| `[` | list open | list literal | `[]` empty list | reserved |
| `{` | record open | record/map literal | `{}` empty record | reserved |
| `(` | group/call | expression group | `()` call/no args | reserved |

## Core v0.2 Set

The first compact runtime should implement only this small set:

| Operator | IR Op | Meaning | Example |
|---|---|---|---|
| `<` | `OP_READ` | read file | `t<prices.txt` |
| `|` | pipeline | pipe value | `t|#|+|!` |
| `?` | `OP_GREP` | keep lines containing arg | `t|?price` |
| `#` | `OP_NUMS` | extract numbers | `t|#` |
| `+` | `OP_SUM` | sum numbers | `t|+` |
| `!` | `OP_OUT` | print value | `t!` |
| `=` | `OP_STORE` | assign expression | `x=1+2` |

Everything else remains reserved until the IR parser exists.

## Compact Examples

Read a file, keep `price` lines, extract numbers, sum, print:

```aiambler
t<prices.txt
t|?price|#|+|!
```

Math:

```aiambler
a=12*7+3
b=(a-7)/4
b!
```

Parallel heavy operation:

```aiambler
fp(3000000)|!
mm(256)|!
```

Future parallel pipe hint:

```aiambler
t<big.log
t|&?error|&#|+|!
```

The future parser should normalize aliases into IR, then the planner decides
whether to run tiny sequential, native fused, or native parallel.

