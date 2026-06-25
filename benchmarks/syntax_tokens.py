from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    group: str
    name: str
    syntax: str


CANDIDATES = [
    Candidate("unit", "function", "function grep_sum(path,needle){<path|?needle|#|+|!}"),
    Candidate("unit", "unit_words", "unit grep_sum path needle = <path|?needle|#|+|!"),
    Candidate("unit", "short_words", "u gs p n=<p|?n|#|+|!"),
    Candidate("unit", "colon", ":gs p n=<p|?n|#|+|!"),
    Candidate("unit", "call_assign", "gs(p,n)=<p|?n|#|+|!"),
    Candidate("unit", "positional_at", "gs=<@0|?@1|#|+|!"),
    Candidate("unit", "positional_min", "$gs=<0|?1|#|+|!"),
    Candidate("object", "obj_word", "obj task{id,title,status}"),
    Candidate("object", "o_word", "o task{id,title,status}"),
    Candidate("object", "colon_shape", "task:{id,title,status}"),
    Candidate("loop", "for_block", "for x in rows { x|#|+ }"),
    Candidate("loop", "loop_words", "loop rows x|#|+"),
    Candidate("loop", "map_star", "*rows|#|+"),
    Candidate("loop", "colon_star", "rows:*#/+"),
    Candidate("parse", "parse_words", "parse csv file as rows"),
    Candidate("parse", "p_words", "p csv file"),
    Candidate("pipeline", "pipe_steps", "src|?warn|@2|#|+"),
    Candidate("pipeline", "fused_steps", "src|?warn@2#+"),
    Candidate("pipeline", "implicit_fused", "?warn@2#+"),
    Candidate("sink", "bang_file", "warn|!>warn_report.txt"),
    Candidate("sink", "dot_file", "warn|.warn_report.txt"),
    Candidate("sink", "dot_suffix", "warn.warn_report.txt"),
    Candidate("sink", "gt_file", "warn|>warn_report.txt"),
    Candidate("sink", "word_file", "warn|write warn_report.txt"),
    Candidate("sink", "console", "err|!"),
    Candidate("sink", "console_suffix", "err!"),
    Candidate("dimension", "numeric_blocks", "3{$src=<f}\n2{$m=<3|@2|#}\n1{$log=<2|+|!}\n0{$out=<1|!}"),
    Candidate("dimension", "d_blocks", "d3{$src=<f}\nd2{$m=<3|@2|#}\nd1{$log=<2|+|!}\nd0{$out=<1|!}"),
    Candidate("dimension", "colon_lines", "3:$src=<f\n2:$m=<3|@2|#\n1:$log=<2|+|!\n0:$out=<1|!"),
    Candidate("dimension", "space_lines", "3 $src=<f\n2 $m=<3|@2|#\n1 $log=<2|+|!\n0 $out=<1|!"),
    Candidate("dimension", "colon_blocks", "3:\n$src=<f\n2:\n$m=<3|@2|#\n1:\n$log=<2|+|!\n0:\n$out=<1|!"),
    Candidate("dimension", "at_blocks", "@3{$src=<f}\n@2{$m=<3|@2|#}\n@1{$log=<2|+|!}\n@0{$out=<1|!}"),
    Candidate("dimension", "dim_words", "dim3 $src=<f\ndim2 $m=<3|@2|#\ndim1 $log=<2|+|!\ndim0 $out=<1|!"),
    Candidate("dimension", "matrix_words", "source $src=<f\nmatrix $m=<source|@2|#\nlog $log=<matrix|+|!\nsystem $out=<log|!"),
    Candidate("dimension_unit", "numeric_unit", "2{$mx=<0|?1|@2|#|+|!}"),
    Candidate("dimension_unit", "colon_unit", "2:$mx=<0|?1|@2|#|+|!"),
    Candidate("dimension_unit", "d_unit", "d2{$mx=<0|?1|@2|#|+|!}"),
    Candidate("dimension_unit", "word_unit", "matrix $mx=<0|?1|@2|#|+|!"),
]


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare token cost of candidate Aiambler syntax forms")
    parser.add_argument("--tiktoken", action="store_true")
    parser.add_argument("--encoding", default="cl100k_base")
    args = parser.parse_args()

    tokenizer = load_tokenizer(args.tiktoken, args.encoding)
    print(f"tokenizer={tokenizer.name}")
    print("group   tok name            syntax")
    current_group = None
    for item in sorted(CANDIDATES, key=lambda x: (x.group, tokenizer.count(x.syntax), x.name)):
        if current_group is not None and item.group != current_group:
            print()
        current_group = item.group
        print(f"{item.group:<7} {tokenizer.count(item.syntax):3d} {item.name:<15} {item.syntax}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
