#!/usr/bin/env bash
# Live check L2 (docs/BUILD-LEDGER.md): the merge guard against real gh on a throwaway private repository.
#
#   scripts/live-gh-wizard.sh OWNER/NAME
#
# Run it by hand. It creates the repository, so it needs a signed-in gh and your yes at every step that changes
# GitHub. It drives the real hook entry point (orchestra_hook.py), not a Claude session, and keeps the run state in a
# scratch directory. See docs/live-gh.md.
set -u -o pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
if [ -f "$ROOT/plugins/orchestra/scripts/orchestra.py" ]; then PLUGIN=$ROOT/plugins/orchestra; else PLUGIN=$ROOT; fi
CLI=$PLUGIN/scripts/orchestra.py
HOOK=$PLUGIN/scripts/orchestra_hook.py
FAILS=0
SESSION=wizard-owner

die() { echo "FAIL $1" >&2; exit 1; }
say() { echo "== $*"; }
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1: $2"; FAILS=$((FAILS + 1)); }

confirm() {
  # Every step that changes GitHub asks first. Anything but y stops the wizard.
  local answer=n
  printf '\n-> %s\n   Proceed? [y/N] ' "$1" >&2
  read -r answer </dev/tty || answer=n
  if [ "$answer" != y ]; then echo 'Stopped: nothing further was changed.' >&2; exit 1; fi
}

orchestra() { python3 "$CLI" "$@"; }

json_field() { python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }

payload() {
  # payload KIND TEXT: the JSON the harness sends the hook. KIND is prompt or merge.
  python3 -c '
import json, sys
kind, text, cwd, session = sys.argv[1:5]
base = dict(cwd=cwd, session_id=session)
if kind == "prompt":
    base.update(hook_event_name="UserPromptSubmit", prompt=text, prompt_id="wizard-1")
else:
    base.update(hook_event_name="PreToolUse", tool_name="Bash", tool_input=dict(command=text))
print(json.dumps(base))' "$1" "$2" "$CLONE" "$SESSION"
}

hook() { python3 "$HOOK" "$1" --harness claude 2>/dev/null; }

approve() {
  # Send the owner's "approved" prompt to the hook and print its reply.
  local reply
  reply=$(payload prompt approved | hook UserPromptSubmit)
  echo "$reply" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("hookSpecificOutput", {}).get("additionalContext", "(no reply)"))'
}

merge_verdict() {
  # merge_verdict COMMAND: "allow", or "deny: REASON", as the hook answers a PreToolUse Bash call.
  payload merge "$1" | hook PreToolUse | python3 -c '
import json, sys
try:
    out = json.load(sys.stdin).get("hookSpecificOutput", {})
except ValueError:
    out = {}
print("deny: " + out.get("permissionDecisionReason", "") if out.get("permissionDecision") == "deny" else "allow")'
}

mark_reviewed() {
  # The wizard tests the merge guard, not the review gate: say every recorded pull request has a clean review.
  python3 -c '
import json, os, sys
path = os.path.join(sys.argv[1], "state.json")
data = json.load(open(path))
for entry in data.get("pull_requests", []):
    entry["reviewed"] = True
tmp = path + ".wizard"
json.dump(data, open(tmp, "w"))
os.replace(tmp, path)' "$STATE"
}

write_ledger() {
  python3 -c '
import datetime, os, sys
sys.path.insert(0, sys.argv[2])
from orchestra_core.engine import AUTONOMY_FIXED
deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).replace(microsecond=0).isoformat()
lines = ["# Autonomy ledger", "", "goal: live merge guard check", "deadline: " + deadline, "",
         "## Completion checks", "", "smoke: true", "", "## Approval boundaries", "", *AUTONOMY_FIXED, ""]
open(os.path.join(sys.argv[1], "autonomy.md"), "w").write("\n".join(lines))' "$STATE" "$PLUGIN/scripts"
}

slug_of() { sed -E 's#^.*[:/]([^/:]+/[^/]+)$#\1#; s#\.git$##' | tr 'A-Z' 'a-z'; }

preflight() {
  [ "$#" -eq 1 ] || die "usage: scripts/live-gh-wizard.sh OWNER/NAME (a repository that does not exist yet)"
  case "$1" in */*/* | */ | /* | *[!A-Za-z0-9._/-]*) die "usage: OWNER/NAME with letters, digits, . _ -" ;; */*) ;; *) die "usage: OWNER/NAME" ;; esac
  command -v gh >/dev/null 2>&1 || die "gh is not installed"
  command -v git >/dev/null 2>&1 || die "git is not installed"
  command -v python3 >/dev/null 2>&1 || die "python3 is not installed"
  [ -f "$CLI" ] && [ -f "$HOOK" ] || die "cannot find orchestra.py and orchestra_hook.py under $PLUGIN"
  gh auth status >/dev/null 2>&1 || die "gh is not signed in: run gh auth login"
  local mine want remote
  want=$(echo "$1" | tr 'A-Z' 'a-z')
  for remote in $(git -C "$ROOT" remote 2>/dev/null); do
    mine=$(git -C "$ROOT" remote get-url "$remote" 2>/dev/null | slug_of)
    [ "$mine" != "$want" ] || die "$1 is this repository's own remote; name a throwaway repository"
  done
  if gh repo view "$1" >/dev/null 2>&1; then die "$1 already exists; name a repository that does not exist yet"; fi
}

setup_clone() {
  WORK=$(mktemp -d)
  CLONE=$WORK/clone
  export XDG_STATE_HOME=$WORK/state-home
  unset ORCHESTRA_STATE_DIR
  mkdir -p "$CLONE" "$XDG_STATE_HOME"
  git -C "$CLONE" init -q -b main
  git -C "$CLONE" config user.name 'Orchestra live wizard'
  git -C "$CLONE" config user.email 'wizard@example.invalid'
  echo 'throwaway repository for the Orchestra merge guard check' >"$CLONE/README.md"
  git -C "$CLONE" add README.md
  git -C "$CLONE" commit -q -m 'initial commit'
  say "scratch directory $WORK (run state in $XDG_STATE_HOME)"
}

create_repo() {
  confirm "create the PRIVATE repository $SLUG and set it as origin"
  (cd "$CLONE" && gh repo create "$SLUG" --private --source . --remote origin >/dev/null) || die "gh repo create failed"
}

push_branches() {
  confirm "push to origin: $*"
  git -C "$CLONE" push -q -u origin "$@" || die "git push $* failed"
  git -C "$CLONE" remote set-head origin --auto >/dev/null 2>&1 || true
}

commit_on() {
  # commit_on BRANCH FILE: one commit on BRANCH, then back on the previous branch.
  git -C "$CLONE" switch -q "$1" && echo "$1 $(date +%s)" >>"$CLONE/$2" && git -C "$CLONE" add -- "$2" \
    && git -C "$CLONE" commit -q -m "$1: change $2" || die "commit on $1 failed"
}

make_pair() {
  # make_pair PARENT CHILD: PARENT on main, CHILD on top of PARENT, each with one commit.
  git -C "$CLONE" switch -q main && git -C "$CLONE" switch -q -c "$1" || die "cannot branch $1"
  commit_on "$1" "$1.txt"
  git -C "$CLONE" switch -q -c "$2" || die "cannot branch $2"
  commit_on "$2" "$2.txt"
  git -C "$CLONE" switch -q main
}

open_pr() {
  # open_pr BASE HEAD: prints the pull request URL.
  confirm "open a pull request: base $1, head $2"
  (cd "$CLONE" && gh pr create --base "$1" --head "$2" --title "wizard: $2 onto $1" --body 'Throwaway pull request for the merge guard check.') \
    || die "gh pr create failed"
}

merge_pr() {
  # merge_pr NUMBER SHA: the guard-printed merge command. A non-zero exit is not fatal: gh can fail to delete a local
  # branch that a worktree holds even though the pull request merged. The caller reads the live state.
  confirm "merge pull request $1 into main with --delete-branch (head $2)"
  (cd "$CLONE" && gh pr merge "$1" --merge --delete-branch --match-head-commit "$2") || echo "   (gh pr merge exited non-zero; reading the live state)"
}

pr_field() { (cd "$CLONE" && gh pr view "$1" --json "$2" --jq ".$2" 2>/dev/null); }

wait_for_base() {
  # wait_for_base NUMBER BASE: poll for a retarget, which GitHub does a moment after the merge.
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    [ "$(pr_field "$1" baseRefName)" = "$2" ] && return 0
    sleep 5
  done
  return 1
}

merge_text() {
  # The command text the hook is asked about. Printed, never run.
  printf 'gh pr merge %s --merge --delete-branch --match-head-commit %s' "$1" "$2"
}

number_of() { echo "${1##*/}"; }

main() {
  preflight "$@"
  SLUG=$1
  say "account: $(gh api user --jq .login)"
  say "throwaway repository: $SLUG"
  setup_clone
  create_repo
  push_branches main

  say "start the run and arm autonomy"
  local started
  started=$(cd "$CLONE" && orchestra start --size medium) || die "orchestra.py start failed"
  LEASE=$(echo "$started" | json_field lease)
  STATE=$(echo "$started" | json_field state)
  make_pair a b
  make_pair a2 b2
  git -C "$CLONE" switch -q a
  write_ledger
  (cd "$CLONE" && orchestra autonomy arm >/dev/null) || die "autonomy arm failed"
  git -C "$CLONE" switch -q main

  say "push the branches and open four pull requests (A on main, B on a, A2 on main, B2 on a2)"
  push_branches a b a2 b2
  URL_A=$(open_pr main a) || exit 1  # a stop inside $(...) ends only the subshell
  URL_B=$(open_pr a b) || exit 1
  URL_A2=$(open_pr main a2) || exit 1
  URL_B2=$(open_pr a2 b2) || exit 1
  local url
  for url in "$URL_A" "$URL_B" "$URL_A2" "$URL_B2"; do
    (cd "$CLONE" && orchestra --lease "$LEASE" pr "$url" >/dev/null) || die "orchestra.py pr $url failed"
  done
  N_A=$(number_of "$URL_A"); N_B=$(number_of "$URL_B"); N_A2=$(number_of "$URL_A2"); N_B2=$(number_of "$URL_B2")

  say "stop the run: it is now unattended and the merge guard gates every merge"
  (cd "$CLONE" && orchestra autonomy disarm >/dev/null) || die "autonomy disarm failed"
  mark_reviewed
  say "the owner types approved; the hook replies:"
  approve

  say "check (a): the head of A moves after approval"
  local old_sha new_sha verdict
  old_sha=$(git -C "$CLONE" rev-parse a)
  commit_on a a.txt
  git -C "$CLONE" switch -q main
  push_branches a
  new_sha=$(git -C "$CLONE" rev-parse a)
  verdict=$(merge_verdict "$(merge_text "$N_A" "$old_sha")")
  case "$verdict" in
    "deny: "*"head moved"*"${new_sha:0:12}"*) pass stale-head-refused ;;
    *) fail stale-head-refused "expected a deny naming the moved head ${new_sha:0:12}, got: $verdict" ;;
  esac

  say "approve again with the new head, then merge A"
  (cd "$CLONE" && orchestra --lease "$LEASE" pr "$URL_A" >/dev/null) || die "orchestra.py pr $URL_A failed"
  mark_reviewed
  approve
  verdict=$(merge_verdict "$(merge_text "$N_A" "$new_sha")")
  [ "$verdict" = allow ] || die "the guard refused the approved merge of A: $verdict"
  merge_pr "$N_A" "$new_sha"
  if [ "$(pr_field "$N_A" state)" != MERGED ]; then die "pull request $N_A did not merge"; fi

  say "check (b): B is retargeted to main after its parent merged"
  if wait_for_base "$N_B" main; then pass child-retargeted; else fail child-retargeted "B still reads base $(pr_field "$N_B" baseRefName)"; fi

  say "check (c): the parent branch a2 is checked out in a worktree when A2 merges"
  git -C "$CLONE" worktree add -q "$WORK/worktree-a2" a2 || die "git worktree add failed"
  local sha_a2 sha_b2
  sha_a2=$(git -C "$CLONE" rev-parse a2)
  sha_b2=$(git -C "$CLONE" rev-parse b2)
  verdict=$(merge_verdict "$(merge_text "$N_A2" "$sha_a2")")
  [ "$verdict" = allow ] || die "the guard refused the approved merge of A2: $verdict"
  merge_pr "$N_A2" "$sha_a2"
  if [ "$(pr_field "$N_A2" state)" != MERGED ]; then die "pull request $N_A2 did not merge"; fi
  sleep 5
  local base
  base=$(pr_field "$N_B2" baseRefName)
  if [ "$base" = main ]; then
    fail worktree-child-denied "GitHub retargeted B2 to main although a2 was in a worktree, so the deny was not reached (ledger row G9 is wrong)"
  else
    verdict=$(merge_verdict "$(merge_text "$N_B2" "$sha_b2")")
    case "$verdict" in
      "deny: "*"gh pr edit $N_B2 --base main"*) pass worktree-child-denied ;;
      *) fail worktree-child-denied "B2 reads base $base; expected a deny naming gh pr edit $N_B2 --base main, got: $verdict" ;;
    esac
  fi

  echo
  if [ "$FAILS" -eq 0 ]; then say "all checks passed"; else say "$FAILS check(s) failed"; fi
  echo "Cleanup is yours. To delete the throwaway repository, run:"
  echo "  gh repo delete $SLUG --yes"
  echo "Scratch files stay in $WORK until you remove that directory."
  [ "$FAILS" -eq 0 ]
}

main "$@"
