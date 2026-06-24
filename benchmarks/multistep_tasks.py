from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks" / "multistep_data"


@dataclass
class Case:
    name: str
    ai: str
    py: str
    awk: str
    ai_cmd: list[str]
    py_cmd: list[str]
    awk_cmd: list[str]


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


def py_emit_helper() -> str:
    return "def emit(x):\n    print(int(x) if x == int(x) else f'{x:.10g}')\n"


def setup() -> list[Case]:
    DATA.mkdir(parents=True, exist_ok=True)

    ops_lines = []
    for i in range(300):
        kind = "ERROR" if i % 6 == 0 else ("WARN" if i % 5 == 0 else "INFO")
        svc = "api" if i % 4 < 2 else "worker"
        ops_lines.append(f"{kind} service={svc} code {500 + i % 23} latency {80 + i % 41} request {i}\n")
    write(DATA / "ops.log", "".join(ops_lines))

    sales_rows = ["date,region,amount,qty\n"]
    regions = ["EU", "US", "APAC"]
    for i in range(360):
        month = "2026-06" if i % 2 else "2026-05"
        region = regions[i % len(regions)]
        sales_rows.append(f"{month}-{(i % 28) + 1:02d},{region},{20 + i % 37}.5,{1 + i % 9}\n")
    write(DATA / "sales.csv", "".join(sales_rows))

    catalog_lines = ["sku,host,price,stock\n"]
    for i in range(160):
        host = "legacy.internal" if i % 3 == 0 else "edge.internal"
        catalog_lines.append(f"{1000 + i},{host},{5 + i % 17}.99,{i % 11}\n")
    write(DATA / "catalog.txt", "".join(catalog_lines))

    ticket_rows = ["id,priority,age,hours\n"]
    for i in range(240):
        priority = "P1" if i % 8 == 0 else ("P2" if i % 3 == 0 else "P3")
        ticket_rows.append(f"T{i:04d},{priority},{1 + i % 21},{0.5 + i % 13:.1f}\n")
    write(DATA / "tickets.csv", "".join(ticket_rows))

    scripts = {
        "incident_triage": (
            "t<benchmarks/multistep_data/ops.log\n"
            "t|?ERROR|#|+|!\n"
            "t|?WARN|#|+/|!\n"
            "t|?api|#|+|!\n"
        ),
        "regional_sales": (
            "t<benchmarks/multistep_data/sales.csv\n"
            "t|?EU|@3|#|+|!\n"
            "t|?2026-06|@4|#|+|!\n"
            "t|@3|#|+/|!\n"
        ),
        "catalog_migration": (
            "t<benchmarks/multistep_data/catalog.txt\n"
            "t|~>legacy.internal=edge.local|!\n"
            "t|@3|#|+/|!\n"
            "t|@4|#|+|!\n"
        ),
        "support_digest": (
            "t<benchmarks/multistep_data/tickets.csv\n"
            "t|?P1|@3|#|+/|!\n"
            "t|?P2|@4|#|+|!\n"
            "t|@4|#|+/|!\n"
        ),
    }
    for name, text in scripts.items():
        write(DATA / f"{name}.ai", text)

    py = {
        "incident_triage": py_emit_helper()
        + """import re\nlines=open('benchmarks/multistep_data/ops.log').read().splitlines()\ndef nums(line): return [float(x) for x in re.findall(r'[-+]?\\d+(?:\\.\\d+)?', line)]\nerr=[n for line in lines if 'ERROR' in line for n in nums(line)]\nwarn=[n for line in lines if 'WARN' in line for n in nums(line)]\napi=[n for line in lines if 'api' in line for n in nums(line)]\nemit(sum(err))\nemit(sum(warn)/len(warn))\nemit(sum(api))\n""",
        "regional_sales": py_emit_helper()
        + """import csv\nrows=list(csv.DictReader(open('benchmarks/multistep_data/sales.csv')))\nemit(sum(float(r['amount']) for r in rows if 'EU' in r['region']))\nemit(sum(float(r['qty']) for r in rows if '2026-06' in r['date']))\namounts=[float(r['amount']) for r in rows]\nemit(sum(amounts)/len(amounts))\n""",
        "catalog_migration": py_emit_helper()
        + """import csv\ntext=open('benchmarks/multistep_data/catalog.txt').read()\nprint(text.replace('legacy.internal','edge.local'), end='')\nrows=list(csv.DictReader(text.splitlines()))\nprices=[float(r['price']) for r in rows]\nstocks=[float(r['stock']) for r in rows]\nemit(sum(prices)/len(prices))\nemit(sum(stocks))\n""",
        "support_digest": py_emit_helper()
        + """import csv\nrows=list(csv.DictReader(open('benchmarks/multistep_data/tickets.csv')))\np1=[float(r['age']) for r in rows if 'P1' in r['priority']]\nemit(sum(p1)/len(p1))\nemit(sum(float(r['hours']) for r in rows if 'P2' in r['priority']))\nhours=[float(r['hours']) for r in rows]\nemit(sum(hours)/len(hours))\n""",
    }
    for name, text in py.items():
        write(DATA / f"{name}.py", text)

    awk_emit = "function emit(x){ if (x == int(x)) printf \"%d\\n\", x; else printf \"%.10g\\n\", x } "
    return [
        Case(
            "incident_triage",
            scripts["incident_triage"],
            py["incident_triage"],
            awk_emit
            + "/ERROR/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) err+=$i} "
            + "/WARN/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) {warn+=$i; wc++}} "
            + "/api/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) api+=$i} "
            + "END{emit(err); emit(warn/wc); emit(api)}",
            ["build/aiambler", str(DATA / "incident_triage.ai")],
            ["python3", str(DATA / "incident_triage.py")],
            ["awk", awk_emit + "/ERROR/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) err+=$i} /WARN/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) {warn+=$i; wc++}} /api/ {for(i=1;i<=NF;i++) if($i ~ /^[-+]?[0-9]+(\\.[0-9]+)?$/) api+=$i} END{emit(err); emit(warn/wc); emit(api)}", "benchmarks/multistep_data/ops.log"],
        ),
        Case(
            "regional_sales",
            scripts["regional_sales"],
            py["regional_sales"],
            awk_emit
            + "BEGIN{FS=\",\"} NR>1{if($2 ~ /EU/) eu+=$3; if($1 ~ /2026-06/) qty+=$4; amount+=$3; c++} END{emit(eu); emit(qty); emit(amount/c)}",
            ["build/aiambler", str(DATA / "regional_sales.ai")],
            ["python3", str(DATA / "regional_sales.py")],
            ["awk", awk_emit + "BEGIN{FS=\",\"} NR>1{if($2 ~ /EU/) eu+=$3; if($1 ~ /2026-06/) qty+=$4; amount+=$3; c++} END{emit(eu); emit(qty); emit(amount/c)}", "benchmarks/multistep_data/sales.csv"],
        ),
        Case(
            "catalog_migration",
            scripts["catalog_migration"],
            py["catalog_migration"],
            awk_emit
            + "BEGIN{FS=\",\"} {line=$0; gsub(/legacy.internal/,\"edge.local\",line); print line} NR>1{price+=$3; pc++; stock+=$4} END{emit(price/pc); emit(stock)}",
            ["build/aiambler", str(DATA / "catalog_migration.ai")],
            ["python3", str(DATA / "catalog_migration.py")],
            ["awk", awk_emit + "BEGIN{FS=\",\"} {line=$0; gsub(/legacy.internal/,\"edge.local\",line); print line} NR>1{price+=$3; pc++; stock+=$4} END{emit(price/pc); emit(stock)}", "benchmarks/multistep_data/catalog.txt"],
        ),
        Case(
            "support_digest",
            scripts["support_digest"],
            py["support_digest"],
            awk_emit
            + "BEGIN{FS=\",\"} NR>1{if($2 ~ /P1/){p1+=$3; p1c++} if($2 ~ /P2/) p2+=$4; hours+=$4; hc++} END{emit(p1/p1c); emit(p2); emit(hours/hc)}",
            ["build/aiambler", str(DATA / "support_digest.ai")],
            ["python3", str(DATA / "support_digest.py")],
            ["awk", awk_emit + "BEGIN{FS=\",\"} NR>1{if($2 ~ /P1/){p1+=$3; p1c++} if($2 ~ /P2/) p2+=$4; hours+=$4; hc++} END{emit(p1/p1c); emit(p2); emit(hours/hc)}", "benchmarks/multistep_data/tickets.csv"],
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
    return out, samples[len(samples) // 2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-step local task benchmark")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--tiktoken", action="store_true")
    parser.add_argument("--encoding", default="o200k_base")
    args = parser.parse_args()

    tokenizer = load_tokenizer(args.tiktoken, args.encoding)
    cases = setup()
    print(f"runs={args.runs} tokenizer={tokenizer.name}")
    print("task              ai_tok py_tok awk_tok ai_ms  py_ms  awk_ms")
    for case in cases:
        ai_out, ai_ms = time_cmd(case.ai_cmd, args.runs)
        py_out, py_ms = time_cmd(case.py_cmd, args.runs)
        awk_out, awk_ms = time_cmd(case.awk_cmd, args.runs)
        if py_out != ai_out or awk_out != ai_out:
            raise RuntimeError(f"{case.name}: output mismatch")
        ai_tok = tokenizer.count(case.ai)
        py_tok = tokenizer.count(case.py)
        awk_tok = tokenizer.count(case.awk)
        print(f"{case.name:<17} {ai_tok:6d} {py_tok:6d} {awk_tok:7d} {ai_ms:5.2f} {py_ms:6.2f} {awk_ms:7.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
