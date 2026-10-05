#!/usr/bin/env python3
"""Run one existing perception test module under a Bazel ``py_test`` target."""
import argparse
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType


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
    os.environ.setdefault("HOME", str(Path("/outputs/home")))
    for value in [str(PACKAGE / "tools")] + roots:
        if value not in os.environ["PATH"].split(os.pathsep):
            os.environ["PATH"] = value + os.pathsep + os.environ["PATH"]


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


class _Raises:
    def __init__(self, exception):
        self.exception = exception

    def __enter__(self):
        return None

    def __exit__(self, exception_type, exception, traceback):
        if exception_type is None:
            raise AssertionError(f"{self.exception.__name__} was not raised")
        return issubclass(exception_type, self.exception)


class _Mark:
    def parametrize(self, names, values):
        names = tuple(name.strip() for name in names.split(",")) if isinstance(names, str) else tuple(names)

        def decorate(function):
            function.__bazel_pytest_params__ = getattr(function, "__bazel_pytest_params__", []) + [(names, values)]
            return function

        return decorate


def _install_pytest_stub():
    module = ModuleType("pytest")
    module.mark = _Mark()
    module.raises = _Raises
    sys.modules.setdefault("pytest", module)


def _load_module(path):
    name = "__bazel_test__." + path.with_suffix("").as_posix().replace("/", ".").replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, PACKAGE / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _pytest_cases(function):
    cases = [((), {})]
    for names, values in getattr(function, "__bazel_pytest_params__", []):
        updated = []
        for args, kwargs in cases:
            for value in values:
                if len(names) == 1:
                    value = (value,)
                case_kwargs = dict(kwargs)
                case_kwargs.update(dict(zip(names, value)))
                updated.append((args, case_kwargs))
        cases = updated
    return cases


def run_pytest(test_path):
    _install_pytest_stub()
    module = _load_module(test_path)
    failures = []
    count = 0
    for name in sorted(dir(module)):
        if not name.startswith("test_"):
            continue
        function = getattr(module, name)
        if not callable(function):
            continue
        for args, kwargs in _pytest_cases(function):
            count += 1
            label = name
            if kwargs:
                label += "[" + ",".join(f"{key}={value!r}" for key, value in kwargs.items()) + "]"
            try:
                function(*args, **kwargs)
            except Exception as exc:
                failures.append((label, exc))
                print(f"FAIL: {label}", file=sys.stderr)
                print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    print(f"Ran {count} tests")
    if failures:
        print(f"FAILED (failures={len(failures)})", file=sys.stderr)
        return 1
    print("OK")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", choices=("unittest", "pytest"), default="unittest")
    parser.add_argument("test_path")
    args = parser.parse_args(argv)
    test_path = Path(args.test_path)
    if test_path.is_absolute() or ".." in test_path.parts:
        parser.error("test_path must stay within the perception package")
    if not (PACKAGE / test_path).is_file():
        parser.error(f"test module not found: {test_path}")

    os.chdir(PACKAGE)
    add_import_roots(test_path)
    if args.framework == "pytest":
        return run_pytest(test_path)
    return run_unittest(test_path)


if __name__ == "__main__":
    raise SystemExit(main())
