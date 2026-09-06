"""Entry point for `python run.py` and for PyInstaller."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from utter.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
