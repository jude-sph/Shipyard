"""Shipyard CLI entry point.

This module exists at the repo root with a unique name to avoid import
collisions with other editable-installed packages that also have a `src/`
directory (e.g. the MBSE project). The pip entry point imports from here
instead of `src.main`, ensuring the correct package is always loaded.
"""
import os
import sys

# Ensure our own src/ is on sys.path before any other src/ package
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def main():
    from src.main import main as _main
    _main()


if __name__ == "__main__":
    main()
