#!/usr/bin/env sh
set -eu

BIN="${1:-build/aiambler}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/math.ai" <<'AI'
a = 12 * 7 + 3
b = (a - 7) / 4
b |> out
AI

"$BIN" "$TMP_DIR/math.ai" > "$TMP_DIR/math.out"
grep -q "^20$" "$TMP_DIR/math.out"

cat > "$TMP_DIR/input.txt" <<'TXT'
price: 120
note: skip me 999
price: 35.5
price: 4.5
TXT

cat > "$TMP_DIR/text.ai" <<AI
text = file.read "$TMP_DIR/input.txt"
text |> grep(price) |> nums |> sum |> out
AI

"$BIN" "$TMP_DIR/text.ai" > "$TMP_DIR/text.out"
grep -q "^160$" "$TMP_DIR/text.out"

cat > "$TMP_DIR/compact.ai" <<AI
t<$TMP_DIR/input.txt
t|?price|#|+|!
AI

"$BIN" "$TMP_DIR/compact.ai" > "$TMP_DIR/compact.out"
grep -q "^160$" "$TMP_DIR/compact.out"

cat > "$TMP_DIR/compact_direct.ai" <<AI
<$TMP_DIR/input.txt|?price|#|+|!
AI

"$BIN" "$TMP_DIR/compact_direct.ai" > "$TMP_DIR/compact_direct.out"
grep -q "^160$" "$TMP_DIR/compact_direct.out"

cat > "$TMP_DIR/compact_out.ai" <<'AI'
a = 12 * 7 + 3
a!
AI

"$BIN" "$TMP_DIR/compact_out.ai" > "$TMP_DIR/compact_out.out"
grep -q "^87$" "$TMP_DIR/compact_out.out"

: > "$TMP_DIR/large.txt"
i=0
while [ "$i" -lt 100 ]; do
    printf 'note: %0100d\n' "$i" >> "$TMP_DIR/large.txt"
    printf 'price: 1\n' >> "$TMP_DIR/large.txt"
    i=$((i + 1))
done

cat > "$TMP_DIR/large_compact.ai" <<AI
t<$TMP_DIR/large.txt
t|?price|#|+|!
AI

"$BIN" "$TMP_DIR/large_compact.ai" > "$TMP_DIR/large_compact.out"
grep -q "^100$" "$TMP_DIR/large_compact.out"

cat > "$TMP_DIR/fp.ai" <<'AI'
fp(1000) |> out
AI

"$BIN" --jobs 2 "$TMP_DIR/fp.ai" > "$TMP_DIR/fp.out"
grep -q "5693.43088" "$TMP_DIR/fp.out"

cat > "$TMP_DIR/mm.ai" <<'AI'
mm(16) |> out
AI

"$BIN" --jobs 2 "$TMP_DIR/mm.ai" > "$TMP_DIR/mm.out"
grep -q "982.7511" "$TMP_DIR/mm.out"

cat > "$TMP_DIR/report.ai" <<'AI'
use b24 ro
t = task? resp:15 status:open
t |> group(project) |> sum(title,deadline,status,risk) |> out.md
AI

"$BIN" "$TMP_DIR/report.ai" > "$TMP_DIR/report.out"
grep -q "Проект 1:" "$TMP_DIR/report.out"
grep -q "title: Проверить гарантию" "$TMP_DIR/report.out"

cat > "$TMP_DIR/dry.ai" <<'AI'
use b24 rw
dry
b24.task.update id:123 stage:3199
AI

"$BIN" "$TMP_DIR/dry.ai" > "$TMP_DIR/dry.out"
grep -q "dry_run: true" "$TMP_DIR/dry.out"
grep -q "requires_confirmation: true" "$TMP_DIR/dry.out"

cat > "$TMP_DIR/denied.ai" <<'AI'
use b24 ro
b24.task.update id:123 stage:3199
AI

if "$BIN" "$TMP_DIR/denied.ai" > "$TMP_DIR/denied.out" 2> "$TMP_DIR/denied.err"; then
    echo "expected ro write denial" >&2
    exit 1
fi
grep -q "ERR_ACCESS_DENIED" "$TMP_DIR/denied.err"
