# Aiambler MVP

Aiambler is a compact executable intent language for AI agents. This repository
contains a v0.1 MVP implementation:

- line-oriented parser and AST;
- interpreter with `ro`, `rw`, `admin` access modes;
- `dry` previews for mutating actions;
- pipeline transforms: `group`, `sum`/`summarize`, `filter`, `sort`, `limit`, `has`;
- outputs: `out.md`, `out.json`, `out.table`, `out.text`;
- mock `b24` and `gm` connectors;
- structured action logs;
- Python compiler.

## Examples

```aiambler
use b24 ro
t = task? resp:15 status:open
t |> group(project) |> sum(title,deadline,status,risk) |> out.md
```

```aiambler
use b24 rw
dry
b24.task.update id:123 stage:3199
```

## CLI

```bash
python -m aiambler.cli script.ai
python -m aiambler.cli --compile-python script.ai
python -m aiambler.cli --logs script.ai
```

