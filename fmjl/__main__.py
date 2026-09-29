"""python -m fmjl: the command line of the fmjl package. See fmjl/__init__.py for the commands."""
import sys

from fmjl import main

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
