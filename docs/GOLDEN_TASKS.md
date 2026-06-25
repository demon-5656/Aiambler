# Golden Agent Tasks

Golden tasks are small realistic prompts that an LLM should solve by emitting
Aiambler instead of doing arithmetic from memory.

They are deliberately ordinary:

- read logs;
- parse CSV/text;
- extract numbers;
- aggregate;
- transform text;
- write console/file output.

Run them with:

```bash
make bench-golden
```

The benchmark compares Aiambler, Python, and AWK outputs, token counts, and
median runtime. Output mismatches fail the run.

## Included Tasks

| Task | Purpose |
| --- | --- |
| `log_error_sum` | Sum numbers from matching log lines. |
| `csv_split_outputs` | Compute two CSV reductions, print one and write one file. |
| `price_average` | Average numbers extracted from matching text lines. |
| `config_replace` | Replace text in a config file. |

These tasks are the product boundary in executable form: the model reasons
about which primitive chain to use, while Aiambler performs exact computation.

