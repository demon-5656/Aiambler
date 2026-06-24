from __future__ import annotations

import argparse
import json
import sys

from .compiler import PythonCompiler
from .errors import AiamblerError
from .parser import AiamblerParser
from .runtime import AiamblerRuntime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aiambler MVP interpreter/compiler")
    parser.add_argument("script", nargs="?", help="Path to .ai script. Reads stdin when omitted.")
    parser.add_argument("--compile-python", action="store_true", help="Compile script to Python instead of executing it.")
    parser.add_argument("--logs", action="store_true", help="Print action logs as JSON after execution.")
    args = parser.parse_args(argv)

    source = open(args.script, encoding="utf-8").read() if args.script else sys.stdin.read()
    try:
        program = AiamblerParser().parse(source)
        if args.compile_python:
            print(PythonCompiler().compile(program), end="")
            return 0
        runtime = AiamblerRuntime()
        result = runtime.execute(program)
        if result is not None:
            print(result)
        if args.logs:
            print(json.dumps(runtime.logs_as_dicts(), ensure_ascii=False, indent=2))
        return 0
    except AiamblerError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

