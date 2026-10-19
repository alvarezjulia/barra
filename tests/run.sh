#!/usr/bin/env bash
# All the tests: the calculator logic (Node) and the Garmin generator (Python).
set -euo pipefail
cd "$(dirname "$0")/.."

# PY may be a path (.venv/bin/python) or a command on PATH (CI passes `python`).
PY=${PY:-.venv/bin/python}
command -v "$PY" >/dev/null || PY=python3

node tests/extract-logic.mjs

failures=0
for t in tests/*.test.mjs; do
  printf '%-34s ' "$(basename "$t")"
  if output=$(node "$t" 2>&1); then
    echo "$output" | tail -1
  else
    echo "FAIL"; echo "$output" | grep -E '^FAIL' -A2 || true
    failures=$((failures+1))
  fi
done

for t in tests/test_*.py; do
  printf '%-34s ' "$(basename "$t")"
  if output=$("$PY" "$t" 2>&1); then
    echo "$output" | tail -1
  else
    echo "FAIL"; echo "$output" | tail -20; failures=$((failures+1))
  fi
done

echo
[ "$failures" -eq 0 ] && echo "all green" || { echo "$failures suite(s) failing"; exit 1; }
