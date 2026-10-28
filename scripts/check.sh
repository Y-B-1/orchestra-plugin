#!/usr/bin/env bash
# Runs every check for this repository locally. CI runs only on manual dispatch, so this script is the gate
# before a push. Usage: scripts/check.sh [--quick]
#   --quick  accepted for compatibility; every check is fast now, so it skips nothing.
# Exit 0 only when every check that ran passed. A check that cannot run here is listed as SKIPPED, never as passed.
set -u
cd "$(dirname "$0")/.."

logs=$(mktemp -d "${TMPDIR:-/tmp}/orchestra-check.XXXXXX")
failed=0
summary=()

py311=$(command -v python3.11 || true)
if [ -z "$py311" ]; then
  echo "python3.11 is not on PATH: install Python 3.11, the oldest version Orchestra supports." >&2
  exit 2
fi
py313=$(command -v python3.13 || true)
if [ -z "$py313" ] && command -v uv >/dev/null 2>&1; then
  py313=$(uv python find 3.13 2>/dev/null || true)
fi

record() {  # name, exit code
  if [ "$2" -eq 0 ]; then summary+=("PASS     $1"); else summary+=("FAIL     $1 (exit $2, log $logs)"); failed=1; fi
}

run() {  # name, command...
  local name=$1; shift
  "$@" >"$logs/$name.log" 2>&1
  record "$name" $?
}

run unittest-3.11 "$py311" -m unittest discover -s tests -p 'test_*.py'
if [ -n "$py313" ]; then
  run unittest-3.13 "$py313" -m unittest discover -s tests -p 'test_*.py'
else
  summary+=("SKIPPED  unittest-3.13 (no Python 3.13: install it, or install uv)")
fi

run hooks-json "$py311" -m json.tool plugins/orchestra/hooks/hooks.json

if command -v claude >/dev/null 2>&1; then
  run validate-plugin claude plugin validate --strict plugins/orchestra
  run validate-marketplace claude plugin validate --strict .
else
  summary+=("SKIPPED  plugin validation (the claude CLI is not on PATH)")
fi

printf '%s\n' "${summary[@]}"
echo "Logs: $logs"
echo "Not covered here: real hook runs in Claude Code. Run python3 scripts/live-check.py before a release."
exit $failed
