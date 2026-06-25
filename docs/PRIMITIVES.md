# Primitive Coverage Matrix

Aiambler grows by adding small verified primitives, not broad language features.

| Task class | Compact form | Readable form | Status |
| --- | --- | --- | --- |
| file source | `<path`, `3 <path` | `file.read path` | done |
| text contains filter | `?needle` | `grep(needle)`, `filter(needle)` | done |
| numeric extraction | `#` | `nums`, `extract_numbers` | done |
| sum | `+` | `sum` | done |
| average | `+/` | `avg`, `average` | done |
| count | `##` | `count`, `len` for text length | done |
| CSV column | `@N` | `pick(N)`, `take(N)` | done |
| TSV column | `@tN` | `pick(tN)` | done |
| replace | `~>old=new` | `replace(old,new)` | done |
| console output | `name!`, `|!` | `out`, `output` | done |
| file output | `name.path`, `|.path`, `!>path` | write current value | done |
| fused pipeline | `?x@2#+` | `filter(x) |> pick(2) |> nums |> sum` | done |
| dimensional order | `3`, `2`, `1`, `0` | `source`, `matrix`, `log`, `system` | partial |
| first write wins | same-dimension assignment | deterministic conflict rule | done |
| strict dimension visibility | Dn reads Dn..max only | namespace isolation | pending |
| parallel dimension tasks | independent same-D tasks | scheduler | pending |
| regex | pending | regex extract/filter | pending |
| JSON path | pending | JSON field extraction | pending |
| date/time parse | pending | date primitive | pending |
| min/max | pending | reductions | pending |
| sort/top/unique | pending | table reducers | pending |
| guarded shell/http | pending | safe external access | pending |

## Current Token-Min Pattern

```aiambler
0 w.r
0 e!
2 w=?warn@2#+
2 e=?err@2#+
3 <events.csv
```

This keeps the high-level agent shape while avoiding Python boilerplate.

