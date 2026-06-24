from __future__ import annotations

import argparse
from dataclasses import dataclass

from agent_tasks import setup


@dataclass
class Tokenizer:
    name: str

    def count(self, text: str) -> int:
        return max(1, round(len(text) / 4))


class TiktokenTokenizer(Tokenizer):
    def __init__(self, encoding_name: str) -> None:
        import tiktoken

        super().__init__(f"tiktoken:{encoding_name}")
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))


def load_tokenizer(prefer_tiktoken: bool, encoding: str) -> Tokenizer:
    if prefer_tiktoken:
        try:
            return TiktokenTokenizer(encoding)
        except Exception as exc:
            print(f"warning: tiktoken unavailable ({exc}); using chars/4")
    return Tokenizer("chars/4")


def main() -> int:
    parser = argparse.ArgumentParser(description="Count generated-code tokens for agent benchmark cases")
    parser.add_argument("--tiktoken", action="store_true", help="Use tiktoken when installed.")
    parser.add_argument("--encoding", default="o200k_base", help="tiktoken encoding name.")
    args = parser.parse_args()

    tokenizer = load_tokenizer(args.tiktoken, args.encoding)
    cases = setup()
    print(f"tokenizer={tokenizer.name}")
    print("task        ai_chars ai_tok py_chars py_tok awk_chars awk_tok py/ai awk/ai")
    for case in cases:
        ai_tok = tokenizer.count(case.ai)
        py_tok = tokenizer.count(case.py)
        awk_tok = tokenizer.count(case.awk)
        print(
            f"{case.name:<11} {len(case.ai):8d} {ai_tok:6d} "
            f"{len(case.py):8d} {py_tok:6d} {len(case.awk):9d} {awk_tok:7d} "
            f"{py_tok / ai_tok:5.2f} {awk_tok / ai_tok:6.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

