from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from agent_tasks import ROOT, setup


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


@dataclass
class Generated:
    text: str
    prompt_tokens: int
    output_tokens: int
    elapsed_ms: float


TASKS = {
    "logs": "Read benchmarks/agent_data/server.log, keep ERROR lines, extract numbers, sum them, output only the number.",
    "finance": "Read benchmarks/agent_data/transactions.csv, keep rows from 2026-06, pick amount column, sum it, output only the number.",
    "prices_avg": "Read benchmarks/agent_data/prices.txt, keep price lines, extract prices, output only the average number.",
    "replace": "Read benchmarks/agent_data/config.txt, replace localhost with 127.0.0.1, output the changed text.",
    "composite": "Read benchmarks/agent_data/data.log, keep metric lines, extract numbers, sum them, output only the number.",
}


def ollama_generate(model: str, prompt: str, timeout: int) -> Generated:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 220},
    }
    start = time.perf_counter()
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return Generated(
        text=data.get("response", "").strip(),
        prompt_tokens=int(data.get("prompt_eval_count") or 0),
        output_tokens=int(data.get("eval_count") or 0),
        elapsed_ms=(time.perf_counter() - start) * 1000,
    )


def prompt_for(task: str, target: str) -> str:
    if target == "ai":
        syntax = (
            "You are a code generator. Output ONLY Aiambler compact code. "
            "No prose. No markdown. No Python. No comments. "
            "Use operators: < read, | pipe, ?contains, # nums, + sum, +/ average, @N CSV field, ~>old=new replace, ! output. "
            "Return exactly the script lines. Example output:\n"
            "t<file.txt\n"
            "t|?price|#|+|!"
        )
    elif target == "py":
        syntax = "Generate only Python 3 code. No markdown. Print the result."
    else:
        syntax = "Generate only one awk command. No markdown."
    return f"{syntax}\nTask: {TASKS[task]}\n"


def clean_code(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
    return text


def run_aiambler(code: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".ai", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    try:
        completed = subprocess.run(["build/aiambler", path], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return completed.returncode, completed.stdout.strip() or completed.stderr.strip()
    finally:
        Path(path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask Ollama to generate Aiambler/Python/awk and compare token counts.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3.6:35b-a3b"))
    parser.add_argument("--task", choices=list(TASKS), default="logs")
    parser.add_argument("--all", action="store_true", help="Run all tasks.")
    parser.add_argument("--targets", default="ai,py,awk", help="Comma-separated targets: ai,py,awk")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--run-ai", action="store_true", help="Execute generated Aiambler code for validation.")
    args = parser.parse_args()

    setup()
    tasks = list(TASKS) if args.all else [args.task]
    targets = [item.strip() for item in args.targets.split(",") if item.strip()]
    print(f"model={args.model}")
    print("task        target prompt_tok out_tok ms      chars status")
    for task in tasks:
        for target in targets:
            prompt = prompt_for(task, target)
            try:
                generated = ollama_generate(args.model, prompt, args.timeout)
            except (urllib.error.URLError, TimeoutError) as exc:
                print(f"{task:<11} {target:<6} ERROR {exc}")
                continue
            code = clean_code(generated.text)
            status = "generated"
            if target == "ai" and args.run_ai:
                rc, out = run_aiambler(code)
                status = f"run:{rc}:{out[:24].replace(chr(10), ' ')}"
            print(
                f"{task:<11} {target:<6} {generated.prompt_tokens:10d} {generated.output_tokens:7d} "
                f"{generated.elapsed_ms:7.0f} {len(code):6d} {status}"
            )
            print("---")
            print(code)
            print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
