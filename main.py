"""Entry point for `python main.py [--diag] [--lang fr]` and the PyInstaller build.

Needs `pip install -e .` first; installed that way, the same entry point is also
the `androidcontextdeploy` command.
"""
import sys

from androidcontextdeploy.app import main

if __name__ == "__main__":
    sys.exit(main())
