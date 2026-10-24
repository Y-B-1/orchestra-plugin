#!/usr/bin/env bash
# Runs every check for this repository locally. CI runs only on manual dispatch, so this script is the gate
# before a push. Usage: scripts/check.sh [--quick]
#   --quick  skips the unit suite (about 7 minutes per Python version); use it while you work, never before a push.
# Exit 0 only when every check that ran passed. A check that cannot run here is listed as SKIPPED, never as passed.
set -u
cd "$(dirname "$0")/.."

quick=0
[ "${1:-}" = "--quick" ] && quick=1
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

# The unit suites are the slow part: start them first, in the background, one per Python version.
pids=()
if [ $quick -eq 0 ]; then
  "$py311" -m unittest discover -s tests >"$logs/unittest-3.11.log" 2>&1 & pids+=("unittest-3.11:$!")
  if [ -n "$py313" ]; then
    "$py313" -m unittest discover -s tests >"$logs/unittest-3.13.log" 2>&1 & pids+=("unittest-3.13:$!")
  else
    summary+=("SKIPPED  unittest-3.13 (no Python 3.13: install it, or install uv)")
  fi
else
  summary+=("SKIPPED  unit suite (--quick)")
fi

run generate "$py311" plugins/orchestra/scripts/generate.py --check
run mod-fixtures "$py311" plugins/orchestra/hooks/mod/fixtures/sync.py --check

# The mod type stubs and tsconfig.json are written by Claude Code when it loads the plugin; they are not tracked.
if [ -f plugins/orchestra/tsconfig.json ] && [ -d plugins/orchestra/.claude-plugin/types ] && command -v npx >/dev/null 2>&1; then
  run mod-typecheck npx -y -p typescript@5 tsc -p plugins/orchestra/tsconfig.json --noEmit
elif [ "$(git rev-parse --git-dir 2>/dev/null)" != "$(git rev-parse --git-common-dir 2>/dev/null)" ]; then
  summary+=("SKIPPED  mod-typecheck GAP (git-ignored stubs: run from the main checkout)")
else
  summary+=("SKIPPED  mod-typecheck (needs npx and the type stubs: load the plugin in Claude Code once)")
fi

if command -v claude >/dev/null 2>&1; then
  run validate-plugin claude plugin validate --strict plugins/orchestra
  run validate-marketplace claude plugin validate --strict .
  run mod-tests claude plugin test plugins/orchestra
else
  summary+=("SKIPPED  plugin validation and mod tests (the claude CLI is not on PATH)")
fi

for entry in ${pids[@]+"${pids[@]}"}; do
  wait "${entry#*:}"
  record "${entry%%:*}" $?
done

printf '%s\n' "${summary[@]}"
echo "Logs: $logs"
echo "Not covered here: Windows (no local host). Run CI by hand (Actions, CI, Run workflow) before a release that changes path or shell handling."
exit $failed
