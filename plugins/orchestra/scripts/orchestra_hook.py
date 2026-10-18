#!/usr/bin/env python3
import os
import subprocess
import sys

if os.name == 'nt' and not sys.flags.utf8_mode:
    # Windows opens text files in the locale encoding unless Python runs in UTF-8 mode: run again in it.
    raise SystemExit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))
from orchestra_core.hooks import main

if __name__ == '__main__':
    sys.exit(main())
