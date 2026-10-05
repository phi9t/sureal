#!/usr/bin/env python3
"""Run every unit-test module of the experiment and separate real failures
from modules this interpreter cannot import.

Each module runs in its own process from the experiment root, the way the
suites are documented to run, so bare module names never leak between areas.
A module is *unavailable* when it fails only because a third-party package
(for example torch, which exists only inside the GPU root) or a sandbox mount
(for example /experiment, which exists only inside Insula) is missing.

    suites.py [AREA ...] [-j N] [--strict]
"""
import argparse
import collections
import concurrent.futures
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MISSING = re.compile(r"^ModuleNotFoundError: No module named '([^'.]+)")
MOUNT = re.compile(r"^FileNotFoundError: \[Errno 2\] No such file or directory: '(/[^/']+)/")
RAISED = re.compile(r'^(\w+\.)*\w*(Error|Exception)\b')
SUMMARY = re.compile(r'^Ran (\d+) tests? in')


def modules(package=PACKAGE):
    listed = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '--', 'test_*.py', '*/test_*.py'],
                            cwd=package, check=True, capture_output=True, text=True).stdout.split('\n')
    return sorted(name for name in listed if name and '/' in name and (Path(package) / name).is_file())


def classify(returncode, output, local):
    """Return (state, detail) for one module's unittest output."""
    lines = output.splitlines()
    ran = next((int(m.group(1)) for m in map(SUMMARY.match, reversed(lines)) if m), 0)
    if returncode == 0:
        return 'passed', ran
    raised = [line for line in lines if RAISED.match(line) and not line.startswith('ImportError: Failed to import')]
    packages = {m.group(1) for m in map(MISSING.match, raised) if m} - local
    mounts = {m.group(1) for m in map(MOUNT.match, raised) if m and not Path(m.group(1)).exists()}
    absent = [MISSING.match(line) and MISSING.match(line).group(1) in packages
              or MOUNT.match(line) and MOUNT.match(line).group(1) in mounts for line in raised]
    if raised and all(absent):
        return 'unavailable', ', '.join(sorted(packages | mounts))
    return 'failed', next((line for line in reversed(lines) if line.startswith('FAILED')), f'exit {returncode}')


def run(name, package, local):
    path = Path(name)
    # A test directory that is itself a package belongs to a self-contained
    # project (the viewer) whose imports are rooted at the package's parent.
    top = path.parent
    while (package / top / '__init__.py').is_file():
        top = top.parent
    roots = [str(package)] + ([str(package / top)] if top != path.parent else [])
    environment = {**os.environ, 'PYTHONPATH': os.pathsep.join(reversed(roots)), 'PYTHONDONTWRITEBYTECODE': '1'}
    command = [sys.executable, '-m', 'unittest', 'discover', '-s', path.parent.as_posix(), '-p', path.name]
    done = subprocess.run(command + (['-t', top.as_posix()] if top != path.parent else []),
                          cwd=package, env=environment, capture_output=True, text=True)
    return name, classify(done.returncode, done.stdout + done.stderr, local), done.stdout + done.stderr


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('areas', nargs='*', help='top-level directories to run (default: all)')
    parser.add_argument('-j', '--jobs', type=int, default=1)
    parser.add_argument('--strict', action='store_true', help='treat unavailable modules as failures')
    parser.add_argument('-v', '--verbose', action='store_true', help='print the output of failed modules')
    arguments = parser.parse_args(argv)
    names = [name for name in modules() if not arguments.areas or name.split('/')[0] in arguments.areas]
    local = {path.stem for path in PACKAGE.rglob('*.py')} | {path.name for path in PACKAGE.iterdir() if path.is_dir()}
    with concurrent.futures.ThreadPoolExecutor(arguments.jobs) as pool:
        results = list(pool.map(lambda name: run(name, PACKAGE, local), names))
    areas = collections.defaultdict(collections.Counter)
    for name, (state, detail), output in results:
        counts = areas[name.split('/')[0]]
        counts[state] += 1
        counts['tests'] += detail if state == 'passed' else 0
        if state != 'passed':
            print(f'{state.upper():12s}{name}: {detail}')
            if state == 'failed' and arguments.verbose:
                print(output)
    print(f'{"area":22s}{"modules":>8s}{"passed":>8s}{"failed":>8s}{"unavail":>8s}{"tests":>7s}')
    total = collections.Counter()
    for name, counts in sorted(areas.items()):
        total.update(counts)
        print(f'{name:22s}{sum(counts[s] for s in ("passed", "failed", "unavailable")):8d}{counts["passed"]:8d}'
              f'{counts["failed"]:8d}{counts["unavailable"]:8d}{counts["tests"]:7d}')
    print(f'{"total":22s}{len(results):8d}{total["passed"]:8d}{total["failed"]:8d}{total["unavailable"]:8d}{total["tests"]:7d}')
    return 1 if total['failed'] or (arguments.strict and total['unavailable']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
