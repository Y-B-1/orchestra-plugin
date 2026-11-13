#!/usr/bin/env python3
"""PreToolUse Bash hook: block destructive git forms. Exit 2 blocks, exit 0 allows."""
import json, os, re, shlex, subprocess, sys

DEFAULT = ("main", "master")
WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def short(args, letter):
    return any(re.fullmatch("-[A-Za-z]+", a) and letter in a for a in args)


def current_branch(cwd):
    r = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip()


def reason(words):
    while words and re.fullmatch(r"\w+=.*", words[0]):
        words = words[1:]
    if not words or os.path.basename(words[0]) != "git":
        return None
    i, cwd = 1, "."
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "-C" and i + 1 < len(words):
            cwd = words[i + 1]
        i += 2 if words[i] in WITH_ARG else 1
    if i >= len(words):
        return None
    sub, args = words[i], words[i + 1:]
    if sub == "push":
        if short(args, "f") or any(a.startswith(("--force", "+")) for a in args):
            return "force push"
        pos = [a for a in args if not a.startswith("-")]
        refs = pos[1:] or ["HEAD"]
        for ref in refs:
            dst = ref.split(":")[-1]
            if dst == "HEAD":
                dst = current_branch(cwd)
            if re.sub(r"^refs/heads/", "", dst) in DEFAULT:
                return "push to the default branch"
    elif sub == "reset" and "--hard" in args:
        return "reset --hard"
    elif sub == "clean" and ("--force" in args or short(args, "f")):
        return "clean -f"
    elif sub == "branch" and ("-D" in args or short(args, "D")):
        return "branch -D"
    elif sub in ("checkout", "restore") and "." in args:
        if not ({"--staged", "-S"} & set(args) and not {"--worktree", "-W"} & set(args)):
            return "checkout . or restore ."
    return None


def main():
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return 0
    words = []
    for tok in tokens + [";"]:
        if re.fullmatch(r"[;&|()]+", tok):
            found = reason(words)
            if found:
                print("BLOCKED: " + found, file=sys.stderr)
                return 2
            words = []
        else:
            words.append(tok)
    return 0


sys.exit(main())
