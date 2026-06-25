from __future__ import annotations

import argparse
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks" / "golden_data"


@dataclass
class Case:
    name: str
    prompt: str
    ai: str
    py: str
    awk: str
    ai_cmd: list[str]
    py_cmd: list[str]
    awk_cmd: list[str]
    files: list[str] = field(default_factory=list)


class Tokenizer:
    name = "chars/4"

    def count(self, text: str) -> int:
        return max(1, round(len(text) / 4))


class TiktokenTokenizer(Tokenizer):
    def __init__(self, encoding: str) -> None:
        import tiktoken

        self.name = f"tiktoken:{encoding}"
        self.encoding = tiktoken.get_encoding(encoding)

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))


def load_tokenizer(use_tiktoken: bool, encoding: str) -> Tokenizer:
    if use_tiktoken:
        try:
            return TiktokenTokenizer(encoding)
        except Exception as exc:
            print(f"warning: tiktoken unavailable ({exc}); using chars/4")
    return Tokenizer()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def setup_data() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

    log = "\n".join(
        f"{'ERROR' if i % 5 == 0 else 'INFO'} code {500 + i % 17} latency {20 + i % 9}"
        for i in range(120)
    ) + "\n"
    write(DATA / "server.log", log)

    events = "kind,value\nerr,7\nwarn,3\nerr,11\nwarn,5\n"
    write(DATA / "events.csv", events)

    prices = "\n".join(
        f"price {10 + i % 7}.5 note ok" if i % 2 == 0 else "skip text"
        for i in range(80)
    ) + "\n"
    write(DATA / "prices.txt", prices)

    config = "api=localhost\ncache=localhost\nmode=prod\n"
    write(DATA / "config.txt", config)


def setup() -> list[Case]:
    setup_data()

    cases = [
        Case(
            "log_error_sum",
            "Read a server log, keep ERROR lines, extract numbers, and print their sum.",
            "3 <benchmarks/golden_data/server.log\n2 e=?ERROR#+\n0 e!\n",
            """import re\ns=0\nfor line in open('benchmarks/golden_data/server.log'):\n    if 'ERROR' in line:\n        s += sum(map(int, re.findall(r'[-+]?\\d+(?:\\.\\d+)?', line)))\nprint(s)\n""",
            """/ERROR/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s+=$i} END{print s}""",
            ["build/aiambler", str(DATA / "log_error_sum.ai")],
            ["python3", str(DATA / "log_error_sum.py")],
            ["awk", "/ERROR/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) s+=$i} END{print s}", "benchmarks/golden_data/server.log"],
        ),
        Case(
            "csv_split_outputs",
            "Read events CSV, sum err values to console and warn values to a report file.",
            "0 w.benchmarks/golden_data/warn_report.txt\n0 e!\n2 w=?warn@2#+\n2 e=?err@2#+\n3 <benchmarks/golden_data/events.csv\n",
            """import csv\nerr=warn=0\nfor row in csv.DictReader(open('benchmarks/golden_data/events.csv')):\n    if row['kind'] == 'err':\n        err += int(row['value'])\n    if row['kind'] == 'warn':\n        warn += int(row['value'])\nopen('benchmarks/golden_data/warn_report.txt','w').write(f'{warn}\\n')\nprint(err)\n""",
            """BEGIN{FS=","} $1=="err"{e+=$2} $1=="warn"{w+=$2} END{print w > "benchmarks/golden_data/warn_report.txt"; print e}""",
            ["build/aiambler", str(DATA / "csv_split_outputs.ai")],
            ["python3", str(DATA / "csv_split_outputs.py")],
            ["awk", 'BEGIN{FS=","} $1=="err"{e+=$2} $1=="warn"{w+=$2} END{print w > "benchmarks/golden_data/warn_report.txt"; print e}', "benchmarks/golden_data/events.csv"],
            ["warn_report.txt"],
        ),
        Case(
            "price_average",
            "Read text rows, keep price rows, extract numbers, and print the average.",
            "3 <benchmarks/golden_data/prices.txt\n2 p=?price#+/\n0 p!\n",
            """import re\nnums=[]\nfor line in open('benchmarks/golden_data/prices.txt'):\n    if 'price' in line:\n        nums += [float(x) for x in re.findall(r'[-+]?\\d+(?:\\.\\d+)?', line)]\nprint(sum(nums)/len(nums))\n""",
            """/price/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) {s+=$i; c++}} END{print s/c}""",
            ["build/aiambler", str(DATA / "price_average.ai")],
            ["python3", str(DATA / "price_average.py")],
            ["awk", "/price/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) {s+=$i; c++}} END{print s/c}", "benchmarks/golden_data/prices.txt"],
        ),
        Case(
            "config_replace",
            "Read a config file, replace localhost with 127.0.0.1, and print it.",
            "<benchmarks/golden_data/config.txt|~>localhost=127.0.0.1|!\n",
            """print(open('benchmarks/golden_data/config.txt').read().replace('localhost','127.0.0.1'), end='')\n""",
            """{gsub(/localhost/,"127.0.0.1"); print}""",
            ["build/aiambler", str(DATA / "config_replace.ai")],
            ["python3", str(DATA / "config_replace.py")],
            ["awk", "{gsub(/localhost/,\"127.0.0.1\"); print}", "benchmarks/golden_data/config.txt"],
        ),
    ]

    for case in cases:
        write(DATA / f"{case.name}.ai", case.ai)
        write(DATA / f"{case.name}.py", case.py)
    return cases


def normalize(text: str) -> str:
    return re.sub(r"\s+$", "", text)


def run_case(case: Case, cmd: list[str], runs: int) -> tuple[str, dict[str, str], float]:
    out = ""
    files: dict[str, str] = {}
    samples = []
    for _ in range(runs):
        for rel in case.files:
            path = DATA / rel
            if path.exists():
                path.unlink()
        start = time.perf_counter()
        completed = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
        samples.append((time.perf_counter() - start) * 1000)
        out = completed.stdout
        files = {rel: (DATA / rel).read_text(encoding="utf-8") for rel in case.files}
    samples.sort()
    return out, files, samples[len(samples) // 2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden LLM-agent task benchmark")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--tiktoken", action="store_true")
    parser.add_argument("--encoding", default="cl100k_base")
    args = parser.parse_args()

    tokenizer = load_tokenizer(args.tiktoken, args.encoding)
    cases = setup()
    print(f"runs={args.runs} tokenizer={tokenizer.name}")
    print("task              ai_tok py_tok awk_tok ai_ms  py_ms  awk_ms")
    for case in cases:
        ai_out, ai_files, ai_ms = run_case(case, case.ai_cmd, args.runs)
        py_out, py_files, py_ms = run_case(case, case.py_cmd, args.runs)
        awk_out, awk_files, awk_ms = run_case(case, case.awk_cmd, args.runs)
        if normalize(ai_out) != normalize(py_out) or normalize(ai_out) != normalize(awk_out):
            raise RuntimeError(f"{case.name}: stdout mismatch")
        if ai_files != py_files or ai_files != awk_files:
            raise RuntimeError(f"{case.name}: file output mismatch")
        print(
            f"{case.name:<17} {tokenizer.count(case.ai):6d} {tokenizer.count(case.py):6d} "
            f"{tokenizer.count(case.awk):7d} {ai_ms:5.2f} {py_ms:6.2f} {awk_ms:7.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
