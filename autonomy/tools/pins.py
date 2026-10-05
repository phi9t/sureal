#!/usr/bin/env python3
"""Compatibility entrypoint for the evidence pin report tool."""
import sys
from pathlib import Path


def _main():
    # Compatibility entrypoint: expose the component import root before Bazel runfiles exist.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evidence.pins import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
