#!/bin/sh
# Hook shells can start with a minimal PATH that lacks Homebrew; search it first.
PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"; export PATH
# --cli runs the Orchestra CLI with the same interpreter discovery (used by the mod).
orchestra_script="orchestra_hook.py"
orchestra_event="$1"
if [ "$1" = "--cli" ]; then
    shift
    orchestra_script="orchestra.py"
fi
# On Windows (Git Bash) $0 can arrive with backslashes, which dirname does not split: use forward slashes.
orchestra_self="$0"
case "$orchestra_self" in
    *\\*) orchestra_self="$(printf '%s' "$orchestra_self" | tr '\\' '/')" ;;
esac
orchestra_script="$(dirname "$orchestra_self")/$orchestra_script"
# Hook shells can resolve Apple's Python 3.9 first, a pyenv or asdf shim can name a version that is not installed, and on
# Windows `python3` is often the Microsoft Store stub. Each candidate must start and report 3.11 or later before it runs
# the hook. `-X utf8` makes text files UTF-8 whatever the system locale is.
orchestra_ok='import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
for orchestra_python in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$orchestra_python" >/dev/null 2>&1 &&
            "$orchestra_python" -c "$orchestra_ok" >/dev/null 2>&1; then
        exec "$orchestra_python" -X utf8 "$orchestra_script" "$@"
    fi
done
# The Windows launcher: `py -3.14` .. `py -3`.
if command -v py >/dev/null 2>&1; then
    for orchestra_version in 3.14 3.13 3.12 3.11 3; do
        if py "-$orchestra_version" -c "$orchestra_ok" >/dev/null 2>&1; then
            exec py "-$orchestra_version" -X utf8 "$orchestra_script" "$@"
        fi
    done
fi
orchestra_missing='Orchestra needs Python 3.11 or later. Install a supported Python runtime.'
# PreToolUse fails closed (exit 2 blocks the call) and the CLI reports an error. Every other event only warns:
# exit 2 on Stop would block the turn from ending, again and again.
case "$orchestra_event" in
    PreToolUse|--cli)
        echo "$orchestra_missing" >&2
        exit 2 ;;
esac
printf '{"systemMessage": "%s"}\n' "$orchestra_missing"
exit 0
