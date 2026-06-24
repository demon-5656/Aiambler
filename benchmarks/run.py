from __future__ import annotations

import argparse
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
        "p95": sorted(samples)[int(runs * 0.95) - 1],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aiambler native speed comparison")
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--rows", type=int, default=100)
    args = parser.parse_args()

    write_fixture(args.rows)

    cases = [
        ("aiambler math", ["build/aiambler", "benchmarks/math.ai"]),
        ("python math", ["python3", "benchmarks/math_std.py"]),
        ("awk math", ["awk", "BEGIN { a = 12 * 7 + 3; b = (a - 7) / 4; print b }"]),
        ("aiambler text", ["build/aiambler", "benchmarks/text.ai"]),
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

    results = [bench(name, cmd, args.runs) for name, cmd in cases]
    base_by_group = {}
    for item in results:
        group = str(item["name"]).split()[-1]
        if str(item["name"]).startswith("aiambler "):
            base_by_group[group] = float(item["median"])
    width = max(len(str(item["name"])) for item in results)
    print(f"runs={args.runs} rows={args.rows}")
    print(f"{'case':<{width}}  {'out':>8}  {'min ms':>9}  {'median ms':>10}  {'mean ms':>9}  {'p95 ms':>8}  {'x ai':>6}")
    for item in results:
        group = str(item["name"]).split()[-1]
        ratio = float(item["median"]) / base_by_group[group]
        print(
            f"{item['name']:<{width}}  {item['out']:>8}  "
            f"{item['min']:9.3f}  {item['median']:10.3f}  {item['mean']:9.3f}  {item['p95']:8.3f}  {ratio:6.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
