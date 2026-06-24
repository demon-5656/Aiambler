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

"$BIN" --dump-ir --dump-plan "$TMP_DIR/compact_direct.ai" > "$TMP_DIR/dump.out" 2> "$TMP_DIR/dump.err"
grep -q "ir line 1: READ(" "$TMP_DIR/dump.err"
grep -q "GREP(price) NUMS SUM OUT" "$TMP_DIR/dump.err"
grep -q "plan line 1: SCAN_SUM_CONTAINS" "$TMP_DIR/dump.err"
grep -q "plan ops line 1: READ\\[SOURCE\\] GREP\\[MAP,ORDERED\\] NUMS\\[MAP,ORDERED\\] SUM\\[REDUCE\\] OUT\\[SINK,ORDERED\\]" "$TMP_DIR/dump.err"
grep -q "^160$" "$TMP_DIR/dump.out"

cat > "$TMP_DIR/compact_finance.ai" <<AI
<$TMP_DIR/input.txt|?price|#|+/|!
AI

"$BIN" --dump-plan "$TMP_DIR/compact_finance.ai" > "$TMP_DIR/avg.out" 2> "$TMP_DIR/avg.err"
grep -q "plan line 1: SCAN_AVG_CONTAINS" "$TMP_DIR/avg.err"
grep -q "^53.33333333$" "$TMP_DIR/avg.out"

cat > "$TMP_DIR/compact_avg_all.ai" <<AI
<$TMP_DIR/input.txt|#|+/|!
AI

"$BIN" --dump-plan "$TMP_DIR/compact_avg_all.ai" > "$TMP_DIR/avg_all.out" 2> "$TMP_DIR/avg_all.err"
grep -q "plan line 1: SCAN_AVG_CONTAINS" "$TMP_DIR/avg_all.err"
grep -q "^289.75$" "$TMP_DIR/avg_all.out"

cat > "$TMP_DIR/csv.txt" <<'TXT'
name,price
book,12.50
pen,3.25
TXT

cat > "$TMP_DIR/compact_pick.ai" <<AI
<$TMP_DIR/csv.txt|@2|#|+|!
AI

"$BIN" "$TMP_DIR/compact_pick.ai" > "$TMP_DIR/compact_pick.out"
grep -q "^15.75$" "$TMP_DIR/compact_pick.out"

cat > "$TMP_DIR/compact_pick_avg.ai" <<AI
<$TMP_DIR/csv.txt|@2|#|+/|!
AI

"$BIN" --dump-plan "$TMP_DIR/compact_pick_avg.ai" > "$TMP_DIR/compact_pick_avg.out" 2> "$TMP_DIR/compact_pick_avg.err"
grep -q "plan line 1: SCAN_AVG_CONTAINS" "$TMP_DIR/compact_pick_avg.err"
grep -q "^7.875$" "$TMP_DIR/compact_pick_avg.out"

cat > "$TMP_DIR/longest.ai" <<AI
<$TMP_DIR/input.txt|##|!
<$TMP_DIR/input.txt|?price|#|+/|!
<$TMP_DIR/input.txt|~>price=cost|!
AI

"$BIN" --dump-ir "$TMP_DIR/longest.ai" > "$TMP_DIR/longest.out" 2> "$TMP_DIR/longest.err"
grep -q "READ($TMP_DIR/input.txt) COUNT OUT" "$TMP_DIR/longest.err"
grep -q "GREP(price) NUMS AVG OUT" "$TMP_DIR/longest.err"
grep -q "REPLACE(price=cost) OUT" "$TMP_DIR/longest.err"
grep -q "^4$" "$TMP_DIR/longest.out"
grep -q "^53.33333333$" "$TMP_DIR/longest.out"
grep -q "cost: 120" "$TMP_DIR/longest.out"

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

: > "$TMP_DIR/parallel.txt"
i=0
while [ "$i" -lt 2000 ]; do
    printf 'note: %0100d\n' "$i" >> "$TMP_DIR/parallel.txt"
    printf 'price: 1\n' >> "$TMP_DIR/parallel.txt"
    i=$((i + 1))
done

cat > "$TMP_DIR/parallel_compact.ai" <<AI
<$TMP_DIR/parallel.txt|?price|#|+|!
AI

"$BIN" --jobs 4 "$TMP_DIR/parallel_compact.ai" > "$TMP_DIR/parallel_compact.out"
grep -q "^2000$" "$TMP_DIR/parallel_compact.out"

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
