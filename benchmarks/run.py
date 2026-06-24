from __future__ import annotations

import argparse
import math
import os
import statistics
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "benchmarks" / "prices.txt"


def write_fixture(rows: int) -> None:
    lines = []
    for i in range(rows):
        lines.append(f"price: {i % 17 + 0.5}\n")
        lines.append(f"note: ignored {i * 1000}\n")
    PRICES.write_text("".join(lines), encoding="utf-8")


def bench(name: str, cmd: list[str], runs: int) -> dict[str, float | str]:
    samples = []
    expected = None
    for _ in range(runs):
        start = time.perf_counter()
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        output = completed.stdout.strip()
        if expected is None:
            expected = output
        elif output != expected:
            raise RuntimeError(f"{name}: unstable output {output!r} != {expected!r}")
        samples.append(elapsed_ms)
    return {
        "name": name,
        "out": expected or "",
        "min": min(samples),
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "p95": sorted(samples)[max(0, min(runs - 1, math.ceil(runs * 0.95) - 1))],
    }


def result_group(name: str) -> str:
    if name == "aiambler compact":
        return "text"
    return name.split()[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aiambler native speed comparison")
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--mode", choices=["small", "heavy"], default="small")
    parser.add_argument("--jobs", default="1,2,4,8")
    parser.add_argument("--fp-iters", type=int, default=20_000_000)
    parser.add_argument("--matrix-size", type=int, default=256)
    args = parser.parse_args()

    write_fixture(args.rows)

    if args.mode == "small":
        cases = [
            ("aiambler math", ["build/aiambler", "benchmarks/math.ai"]),
            ("python math", ["python3", "benchmarks/math_std.py"]),
            ("awk math", ["awk", "BEGIN { a = 12 * 7 + 3; b = (a - 7) / 4; print b }"]),
            ("aiambler text", ["build/aiambler", "benchmarks/text.ai"]),
            ("aiambler compact", ["build/aiambler", "benchmarks/compact_text.ai"]),
            ("python text", ["python3", "benchmarks/text.py"]),
            (
                "awk text",
                [
                    "awk",
                    "/price/ { for (i = 1; i <= NF; i++) if ($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s += $i } END { print s }",
                    "benchmarks/prices.txt",
                ],
            ),
        ]
    else:
        fp_script = ROOT / "benchmarks" / "generated_fp.ai"
        mm_script = ROOT / "benchmarks" / "generated_mm.ai"
        fp_script.write_text(f"fp({args.fp_iters}) |> out\n", encoding="utf-8")
        mm_script.write_text(f"mm({args.matrix_size}) |> out\n", encoding="utf-8")
        jobs = [int(item) for item in args.jobs.split(",") if item.strip()]
        cases = []
        for job in jobs:
            cases.append((f"aiambler-j{job} fp", ["build/aiambler", "--jobs", str(job), str(fp_script.relative_to(ROOT))]))
        cases.append(("python fp", ["python3", "benchmarks/fp_std.py", str(args.fp_iters)]))
        for job in jobs:
            cases.append((f"aiambler-j{job} mm", ["build/aiambler", "--jobs", str(job), str(mm_script.relative_to(ROOT))]))
        cases.append(("python mm", ["python3", "benchmarks/mm_std.py", str(args.matrix_size)]))
        os.environ.setdefault("OPENBLAS_NUM_THREADS", str(max(jobs)))
        os.environ.setdefault("OMP_NUM_THREADS", str(max(jobs)))
        cases.append(("numpy mm", ["python3", "benchmarks/mm_numpy.py", str(args.matrix_size)]))

    results = [bench(name, cmd, args.runs) for name, cmd in cases]
    base_by_group = {}
    for item in results:
        group = result_group(str(item["name"]))
        if str(item["name"]).startswith("aiambler ") or str(item["name"]).startswith("aiambler-j1 "):
            base_by_group.setdefault(group, float(item["median"]))
    width = max(len(str(item["name"])) for item in results)
    print(f"runs={args.runs} rows={args.rows}")
    print(f"{'case':<{width}}  {'out':>8}  {'min ms':>9}  {'median ms':>10}  {'mean ms':>9}  {'p95 ms':>8}  {'x ai':>6}")
    for item in results:
        group = result_group(str(item["name"]))
        ratio = float(item["median"]) / base_by_group[group]
        print(
            f"{item['name']:<{width}}  {item['out']:>8}  "
            f"{item['min']:9.3f}  {item['median']:10.3f}  {item['mean']:9.3f}  {item['p95']:8.3f}  {ratio:6.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
