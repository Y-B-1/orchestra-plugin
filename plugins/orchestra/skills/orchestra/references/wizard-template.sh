#!/usr/bin/env bash
# Wizard template. Fill the STAGES section only; never edit the library.
# DRY_RUN=1 changes nothing. ENV_FILE=path picks the env file (default .env).
set -euo pipefail
ENV_FILE="${ENV_FILE:-.env}"; DRY_RUN="${DRY_RUN:-0}"; N=0; DONE=""

# ---- library ----
fail() { echo "stopped: $*" >&2; exit 1; }
stage() { N=$((N + 1)); [ -t 1 ] && clear || echo; echo "== Stage $N of $TOTAL: $1 =="; }
url() { echo "Open: $1"; }                  # call before ask: the value is found there
yes() { local a; printf '%s [y/N] ' "$1"; read -r a || fail "end of input"; [ "$a" = y ] || fail "not confirmed"; }
env_get() {                                # print the decoded saved value of KEY, if any
  [ -f "$ENV_FILE" ] || return 0
  local v; v=$(grep "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-) || true
  case "$v" in \'*\') v=${v#\'}; v=${v%\'}; v=${v//\'\\\'\'/\'} ;; esac
  printf '%s' "$v"
}
env_upsert() {                             # env_upsert KEY VALUE: one line, single-quoted
  local f="$ENV_FILE" tmp q
  if [ "$DRY_RUN" = 1 ]; then echo "dry run: would set $1"; return 0; fi
  while [ -L "$f" ]; do f=$(readlink "$f"); done   # write through a symlink
  [ -f "$f" ] || : > "$f"
  q=${2//\'/\'\\\'\'}; tmp=$(mktemp)
  { grep -v "^$1=" "$f" || true; printf "%s='%s'\n" "$1" "$q"; } > "$tmp"
  cat "$tmp" > "$f"; rm -f "$tmp"; echo "saved $1"
}
ask() {                                    # ask KEY "prompt": the saved value is the default
  local d v; d=$(env_get "$1"); printf '%s [%s]: ' "$2" "$d"
  read -r v || fail "end of input"; env_upsert "$1" "${v:-$d}"
}
ask_secret() {                             # hidden input; the value is never printed
  local d v; d=$(env_get "$1"); printf '%s%s: ' "$2" "${d:+ (saved; Enter keeps it)}"
  read -r -s v || fail "end of input"; echo; env_upsert "$1" "${v:-$d}"
}
run_stage() { "$1"; yes "Stage $N done?"; DONE="$DONE $1"; }
summary() { local s; for s in $STAGES; do case "$DONE " in *" $s "*) ;; *) echo "not done: $s";; esac; done; }

# ---- STAGES (fill; one function per stage, listed in order) ----
STAGES="stage_example"
stage_example() {
  stage "Example token"
  url "https://example.com/settings/tokens"
  ask_secret EXAMPLE_TOKEN "Paste the token"
}
# ---- end STAGES ----

main() {
  local s; TOTAL=$(echo $STAGES | wc -w | tr -d ' ')
  trap summary EXIT
  for s in $STAGES; do run_stage "$s"; done
}
[ -n "${WIZARD_SOURCE_ONLY:-}" ] || main "$@"
