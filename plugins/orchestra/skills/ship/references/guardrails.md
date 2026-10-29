# Git guardrails

Only when the owner asks. This is a hook in the owner's project, separate from Orchestra's own guard, which stays merge-only. Orchestra installs this only when the owner asks, and never in its own plugin.

The hook must never block a plain push of a feature branch or opening a PR, because Orchestra's finish step and the /goal Stop hook push the branch. Block only destructive forms: a force push (`--force`, `-f`, `--force-with-lease`, `+refspec`), a push to the default branch (named, or a bare push while on it), `reset --hard`, `clean -f`, `branch -D`, `checkout .` and `restore .` (unstaging with `restore --staged .` stays allowed).

1. Ask the owner for the scope: this project or all projects.
2. Write the script below to `.claude/hooks/git-guardrails.py` (or `~/.claude/hooks/git-guardrails.py`) and `chmod +x` it. Replace `main` and `master` in `DEFAULT` if the default branch has another name.
3. Install it as a PreToolUse Bash hook in that scope's settings. If the settings file exists, merge the hook into its existing `hooks.PreToolUse` array and never overwrite other settings.
4. Test it. Pipe `{"tool_input":{"command":"git push --force origin main"}}` and expect exit 2. Pipe `cd repo` and `git reset --hard` on two lines and expect exit 2. Pipe `git push origin feature-x` and `gh pr create` the same way and expect exit 0.

```python
#!/usr/bin/env python3
import json, re, subprocess, sys

DEFAULT = ("main", "master")
cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
reason = None
for part in re.split(r"&&|\|\||;|\||\n", cmd):
    t = part.split()
    if t[:1] != ["git"]:
        continue
    rest = t[1:]
    if "push" in rest:
        args = rest[rest.index("push") + 1:]
        if any(a in ("--force", "-f") or a.startswith("--force-with-lease") or a.startswith("+") for a in args):
            reason = "force push"
        elif any(a.split(":")[-1] in DEFAULT or a.split(":")[-1].endswith("/" + d) for a in args for d in DEFAULT):
            reason = "push to the default branch"
        elif [a for a in args if not a.startswith("-")][1:2] in ([], ["HEAD"]):
            here = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
            if here in DEFAULT:
                reason = "push to the default branch"
    elif "reset" in rest and "--hard" in rest:
        reason = "reset --hard"
    elif "clean" in rest and any(a.startswith("-") and not a.startswith("--") and "f" in a for a in rest):
        reason = "clean -f"
    elif "branch" in rest and "-D" in rest:
        reason = "branch -D"
    elif ("checkout" in rest or "restore" in rest) and "." in rest and "--staged" not in rest:
        reason = "checkout . or restore ."
    if reason:
        break
if reason:
    print("BLOCKED: " + reason, file=sys.stderr)
    sys.exit(2)
sys.exit(0)
```
