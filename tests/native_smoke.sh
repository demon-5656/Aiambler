#!/usr/bin/env sh
set -eu

BIN="${1:-build/aiambler}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

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

