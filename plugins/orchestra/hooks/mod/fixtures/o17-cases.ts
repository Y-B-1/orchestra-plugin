// O17 parity cases, copied from the B2-r4 corpus additions (SPEC A5, O17) so the TypeScript classifier is tested
// against them before that branch merges. After the merge they are also part of config/guard-corpus.json.

import type { CorpusCase } from './guard-fixtures.js';

export const O17_CASES: CorpusCase[] = [
 {
  "id": "inline-r4-1",
  "input": {
   "command": "{ git reset --hard; }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-2",
  "input": {
   "command": "if true; then git reset --hard; fi"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-3",
  "input": {
   "command": "! git reset --hard"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-4",
  "input": {
   "command": "{ bash <<< 'git reset --hard'; }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-5",
  "input": {
   "command": "{ eval \"$(echo 'git reset --hard')\"; }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-6",
  "input": {
   "command": "{ bash <(echo 'git reset --hard'); }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-7",
  "input": {
   "command": "{ eval $(echo git reset --hard); }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-8",
  "input": {
   "command": "if true; then eval $(echo git reset --hard); fi"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-9",
  "input": {
   "command": "! eval $(echo git reset --hard)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-10",
  "input": {
   "command": "! bash <<< 'git reset --hard'"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-11",
  "input": {
   "command": "eval $({ echo git reset --hard; })"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-12",
  "input": {
   "command": "while true; do git reset --hard; done"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-13",
  "input": {
   "command": "until false; do git reset --hard; done"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-14",
  "input": {
   "command": "if false; then :; elif true; then git reset --hard; else :; fi"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-15",
  "input": {
   "command": "if true; then :; else git reset --hard; fi"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-16",
  "input": {
   "command": "time git reset --hard"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-17",
  "input": {
   "command": "case x in x) git reset --hard;; esac"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-18",
  "input": {
   "command": "case x in (x) git reset --hard;; esac"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-19",
  "input": {
   "command": "case x in a|x) git reset --hard;; esac"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-20",
  "input": {
   "command": "{ bash -c 'git reset --hard'; }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-21",
  "input": {
   "command": "if true; then bash -c 'git reset --hard'; fi"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-22",
  "input": {
   "command": "! { git reset --hard; }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-23",
  "input": {
   "command": "for i in 1; do git reset --hard; done"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-24",
  "input": {
   "command": "if true; then bash <<< 'git reset --hard'; fi"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-25",
  "input": {
   "command": "{ bash -c \"$(echo 'git reset --hard')\"; } 2>&1"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-26",
  "input": {
   "command": "{ eval \"$(ssh-agent -s)\"; }"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-27",
  "input": {
   "command": "if git diff --quiet; then echo clean; fi"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-28",
  "input": {
   "command": "if true; then eval \"$(pyenv init -)\"; fi"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-29",
  "input": {
   "command": "while read l; do echo \"$l\"; done"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-30",
  "input": {
   "command": "time git status"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-31",
  "input": {
   "command": "case x in x) echo y;; esac"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-32",
  "input": {
   "command": "! git diff --quiet"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-33",
  "input": {
   "command": "eval $((echo git reset --hard) )"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-34",
  "input": {
   "command": "eval \"$((echo git reset --hard) )\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-35",
  "input": {
   "command": "bash -c \"$((echo git reset --hard) )\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-36",
  "input": {
   "command": "echo $((1+2))"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-37",
  "input": {
   "command": "echo $(( $(wc -l < f) + 1 ))"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-38",
  "input": {
   "command": "bash -c \"echo $(( $(echo 1) ))\""
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-39",
  "input": {
   "command": "eval $(case x in x) echo git reset --hard;; esac)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-40",
  "input": {
   "command": "bash -c \"$(case x in x) echo git reset --hard;; esac)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-41",
  "input": {
   "command": "bash -c $(case x in x) echo 'git reset --hard';; esac)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-42",
  "input": {
   "command": "eval \"$(case x in x) echo git reset --hard;; esac)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-43",
  "input": {
   "command": "eval $(case x in (x) echo git reset --hard;; esac)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-44",
  "input": {
   "command": "eval $(# )\necho git reset --hard)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-45",
  "input": {
   "command": "bash -c \"$(# )\necho git reset --hard)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-46",
  "input": {
   "command": "eval $(echo git reset --hard # )\n)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-47",
  "input": {
   "command": "eval \"$(echo $'x\\')' >/dev/null; echo git reset --hard)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-48",
  "input": {
   "command": "bash -c \"$(echo $'x\\')' >/dev/null; echo git reset --hard)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-49",
  "input": {
   "command": "eval \"$(echo $'x\\')'; echo git reset --hard)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-50",
  "input": {
   "command": "bash -c \"$(: $'\\')'; echo git reset --hard)\""
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-51",
  "input": {
   "command": "eval \"$(echo $'a\\'b')\""
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-52",
  "input": {
   "command": "bash -c \"echo $(case x in x) echo y;; esac)\""
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-53",
  "input": {
   "command": "eval \"$(echo 'a) b')\""
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-54",
  "input": {
   "command": "eval \"$(npm completion)\" # comment ( here"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-55",
  "input": {
   "command": "echo 'git reset --hard' | (cd x; cat) | bash"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-56",
  "input": {
   "command": "echo 'git reset --hard' | { cat; } | { cd y; bash; }"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-57",
  "input": {
   "command": "echo 'git reset --hard' | (cd x; cat) | (cd y; bash)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-58",
  "input": {
   "command": "echo 'git reset --hard' | { cd x; cat; } | bash"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-59",
  "input": {
   "command": "echo 'git reset --hard' | (cat) | bash"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-60",
  "input": {
   "command": "echo 'git reset --hard' | cat | (cd y; bash)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-61",
  "input": {
   "command": "echo 'git reset --hard' | (cd x; cat | bash)"
  },
  "class": "deny"
 },
 {
  "id": "inline-r4-62",
  "input": {
   "command": "ls | (cd x; wc -l)"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-63",
  "input": {
   "command": "echo 'git status' | (cd x; cat) | bash"
  },
  "class": "allow"
 },
 {
  "id": "inline-r4-64",
  "input": {
   "command": "ls | (cd x; cat) | wc -l"
  },
  "class": "allow"
 }
];
