#!/bin/sh
# Hook shells can resolve Apple's Python 3.9 first. Select a supported runtime.
for orchestra_python in python3 python3.14 python3.13 python3.12 python3.11; do
    if command -v "$orchestra_python" >/dev/null 2>&1 && "$orchestra_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
        exec "$orchestra_python" "$(dirname "$0")/orchestra_hook.py" "$@"
    fi
done
echo 'Orchestra needs Python 3.11 or later. Install a supported Python runtime.' >&2
exit 2
