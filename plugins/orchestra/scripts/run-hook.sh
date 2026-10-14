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
orchestra_script="$(dirname "$0")/$orchestra_script"
# Hook shells can resolve Apple's Python 3.9 first, and a pyenv or asdf shim can name a version that is not
# installed. Each candidate must start and report 3.11 or later before it runs the hook.
for orchestra_python in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$orchestra_python" >/dev/null 2>&1 &&
            "$orchestra_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
        exec "$orchestra_python" "$orchestra_script" "$@"
    fi
done
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
