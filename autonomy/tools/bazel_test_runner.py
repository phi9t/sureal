#!/usr/bin/env python3
"""Run one existing perception test module under a Bazel ``py_test`` target.

This is a bridge while the source tree is still unreorganised: it resolves the
test path back to the package tree and exposes the package roots to in-place
imports. Ticket 26 should remove this runner when tests have native Bazel deps.
"""
import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


def import_roots(test_path):
    module_dir = PACKAGE / test_path.parent
    top = test_path.parent
    while (PACKAGE / top / "__init__.py").is_file():
        top = top.parent
    roots = [PACKAGE]
    if module_dir != PACKAGE:
        roots.append(module_dir)
    if top != test_path.parent:
        roots.append(PACKAGE / top)
    return list(dict.fromkeys(roots))


def add_import_roots(test_path):
    roots = [str(root) for root in import_roots(test_path)]
    for value in roots:
        if value not in sys.path:
            sys.path.insert(0, value)
    existing = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(roots + ([existing] if existing else []))


def run_unittest(test_path):
    top = test_path.parent
    while (PACKAGE / top / "__init__.py").is_file():
        top = top.parent
    kwargs = {}
    if top != test_path.parent:
        kwargs["top_level_dir"] = str(PACKAGE / top)
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(PACKAGE / test_path.parent),
        pattern=test_path.name,
        **kwargs,
    )
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


def run_pytest(test_path):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", test_path.as_posix()],
        cwd=PACKAGE,
        env=os.environ,
    ).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pytest", action="store_true")
    parser.add_argument("test_path")
    args = parser.parse_args(argv)
    test_path = Path(args.test_path)
    if test_path.is_absolute() or ".." in test_path.parts:
        parser.error("test_path must stay within the perception package")
    if not (PACKAGE / test_path).is_file():
        parser.error(f"test module not found: {test_path}")

    os.chdir(PACKAGE)
    add_import_roots(test_path)
    if args.pytest:
        return run_pytest(test_path)
    return run_unittest(test_path)


if __name__ == "__main__":
    raise SystemExit(main())
