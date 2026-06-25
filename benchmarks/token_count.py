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
    parser.add_argument("--encoding", default="cl100k_base", help="tiktoken encoding name.")
    args = parser.parse_args()

    tokenizer = load_tokenizer(args.tiktoken, args.encoding)
    cases = setup()
    print(f"tokenizer={tokenizer.name}")
    print("task        compact verbose token_min best best_form python awk  py/best awk/best")
    for case in cases:
        compact_tok = tokenizer.count(case.ai)
        verbose_tok = tokenizer.count(case.ai_verbose)
        token_min_tok = tokenizer.count(case.ai_min)
        py_tok = tokenizer.count(case.py)
        awk_tok = tokenizer.count(case.awk)
        candidates = {
            "compact": compact_tok,
            "verbose": verbose_tok,
            "token_min": token_min_tok,
        }
        best_form, best_tok = min(candidates.items(), key=lambda item: item[1])
        print(
            f"{case.name:<11} {compact_tok:7d} {verbose_tok:7d} {token_min_tok:9d} {best_tok:4d} "
            f"{best_form:<9} {py_tok:6d} {awk_tok:3d} {py_tok / best_tok:8.2f} {awk_tok / best_tok:8.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
