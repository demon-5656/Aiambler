from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks" / "agent_data"


@dataclass
class Case:
    name: str
    ai: str
    ai_verbose: str
    ai_min: str
    py: str
    awk: str
    ai_cmd: list[str]
    py_cmd: list[str]
    awk_cmd: list[str]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def setup() -> list[Case]:
    DATA.mkdir(parents=True, exist_ok=True)

    server_log = "\n".join(
        f"{'ERROR' if i % 10 == 0 else 'INFO'} code {500 + i % 37} request {i}" for i in range(1000)
    ) + "\n"
    write(DATA / "server.log", server_log)

    tx_rows = ["date,amount,category"]
    for i in range(1000):
        month = "2026-06" if i % 3 else "2026-05"
        tx_rows.append(f"{month}-{(i % 28) + 1:02d},{(i % 19) + 0.5:.1f},cat{i % 5}")
    write(DATA / "transactions.csv", "\n".join(tx_rows) + "\n")

    prices = "\n".join(f"Product: price ${1 + (i % 23) + 0.99:.2f}" for i in range(1000)) + "\n"
    write(DATA / "prices.txt", prices)

    config = "\n".join(
        f"service{i}.host=localhost" if i % 4 == 0 else f"service{i}.host=example.com" for i in range(200)
    ) + "\n"
    write(DATA / "config.txt", config)

    data_log = "\n".join(f"{'metric' if i % 7 == 0 else 'skip'} value {i % 41}" for i in range(1000)) + "\n"
    write(DATA / "data.log", data_log)

    scripts = {
        "logs": "<benchmarks/agent_data/server.log|?ERROR|#|+|!\n",
        "finance": "<benchmarks/agent_data/transactions.csv|?2026-06|@2|#|+|!\n",
        "prices": "<benchmarks/agent_data/prices.txt|?price|#|+/|!\n",
        "replace": "<benchmarks/agent_data/config.txt|~>localhost=127.0.0.1|!\n",
        "composite": "<benchmarks/agent_data/data.log|?metric|#|+|!\n",
    }
    verbose_scripts = {
        "logs": "<benchmarks/agent_data/server.log|filter(ERROR)|extract_numbers|sum|output\n",
        "finance": "<benchmarks/agent_data/transactions.csv|filter(2026-06)|pick(2)|extract_numbers|sum|output\n",
        "prices": "<benchmarks/agent_data/prices.txt|filter(price)|extract_numbers|average|output\n",
        "replace": "<benchmarks/agent_data/config.txt|replace(localhost,127.0.0.1)|output\n",
        "composite": "<benchmarks/agent_data/data.log|filter(metric)|extract_numbers|sum|output\n",
    }
    token_min_scripts = scripts.copy()
    for name, text in scripts.items():
        write(DATA / f"{name}.ai", text)
        write(DATA / f"{name}_verbose.ai", verbose_scripts[name])
        write(DATA / f"{name}_min.ai", token_min_scripts[name])

    py = {
        "logs": """import re\ns=0\nfor line in open('benchmarks/agent_data/server.log'):\n    if 'ERROR' in line:\n        s += sum(map(int, re.findall(r'[-+]?\\d+(?:\\.\\d+)?', line)))\nprint(s)\n""",
        "finance": """import csv\ns=0.0\nfor row in csv.DictReader(open('benchmarks/agent_data/transactions.csv')):\n    if row['date'].startswith('2026-06'):\n        s += float(row['amount'])\nprint(int(s) if s == int(s) else s)\n""",
        "prices": """import re\nnums=[]\nfor line in open('benchmarks/agent_data/prices.txt'):\n    if 'price' in line:\n        nums += [float(x) for x in re.findall(r'[-+]?\\d+(?:\\.\\d+)?', line)]\nprint(sum(nums)/len(nums))\n""",
        "replace": """print(open('benchmarks/agent_data/config.txt').read().replace('localhost','127.0.0.1'), end='')\n""",
        "composite": """import re\ns=0\nfor line in open('benchmarks/agent_data/data.log'):\n    if 'metric' in line:\n        s += sum(map(int, re.findall(r'[-+]?\\d+(?:\\.\\d+)?', line)))\nprint(s)\n""",
    }
    for name, text in py.items():
        write(DATA / f"{name}.py", text)

    return [
        Case(
            "logs",
            scripts["logs"],
            verbose_scripts["logs"],
            token_min_scripts["logs"],
            py["logs"],
            "awk '/ERROR/ { for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s+=$i } END{print s}' benchmarks/agent_data/server.log",
            ["build/aiambler", str(DATA / "logs.ai")],
            ["python3", str(DATA / "logs.py")],
            ["awk", "/ERROR/ { for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s+=$i } END{print s}", "benchmarks/agent_data/server.log"],
        ),
        Case(
            "finance",
            scripts["finance"],
            verbose_scripts["finance"],
            token_min_scripts["finance"],
            py["finance"],
            "awk -F, '$1 ~ /^2026-06/ {s+=$2} END{print s}' benchmarks/agent_data/transactions.csv",
            ["build/aiambler", str(DATA / "finance.ai")],
            ["python3", str(DATA / "finance.py")],
            ["awk", "-F,", "$1 ~ /^2026-06/ {s+=$2} END{print s}", "benchmarks/agent_data/transactions.csv"],
        ),
        Case(
            "prices_avg",
            scripts["prices"],
            verbose_scripts["prices"],
            token_min_scripts["prices"],
            py["prices"],
            "awk '/price/ { for(i=1;i<=NF;i++) if($i ~ /[0-9]+\\.[0-9]+/) {gsub(/[^0-9.]/,\"\",$i); s+=$i; c++}} END{print s/c}' benchmarks/agent_data/prices.txt",
            ["build/aiambler", str(DATA / "prices.ai")],
            ["python3", str(DATA / "prices.py")],
            ["awk", "/price/ { for(i=1;i<=NF;i++) if($i ~ /[0-9]+\\.[0-9]+/) {gsub(/[^0-9.]/,\"\",$i); s+=$i; c++}} END{print s/c}", "benchmarks/agent_data/prices.txt"],
        ),
        Case(
            "replace",
            scripts["replace"],
            verbose_scripts["replace"],
            token_min_scripts["replace"],
            py["replace"],
            "awk '{gsub(/localhost/,\"127.0.0.1\"); print}' benchmarks/agent_data/config.txt",
            ["build/aiambler", str(DATA / "replace.ai")],
            ["python3", str(DATA / "replace.py")],
            ["awk", "{gsub(/localhost/,\"127.0.0.1\"); print}", "benchmarks/agent_data/config.txt"],
        ),
        Case(
            "composite",
            scripts["composite"],
            verbose_scripts["composite"],
            token_min_scripts["composite"],
            py["composite"],
            "awk '/metric/ { for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s+=$i } END{print s}' benchmarks/agent_data/data.log",
            ["build/aiambler", str(DATA / "composite.ai")],
            ["python3", str(DATA / "composite.py")],
            ["awk", "/metric/ { for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s+=$i } END{print s}", "benchmarks/agent_data/data.log"],
        ),
    ]


def time_cmd(cmd: list[str], runs: int) -> tuple[str, float]:
    out = ""
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        completed = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
        samples.append((time.perf_counter() - start) * 1000)
        out = completed.stdout.strip()
    samples.sort()
    return out[:24].replace("\n", "\\n"), samples[len(samples) // 2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=50)
    args = parser.parse_args()

    cases = setup()
    print(f"runs={args.runs}")
    print("task         ai_ms  py_ms  awk_ms  out")
    for case in cases:
        ai_out, ai_ms = time_cmd(case.ai_cmd, args.runs)
        _py_out, py_ms = time_cmd(case.py_cmd, args.runs)
        _awk_out, awk_ms = time_cmd(case.awk_cmd, args.runs)
        print(f"{case.name:<11} {ai_ms:6.2f} {py_ms:6.2f} {awk_ms:7.2f}  {ai_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
