#!/usr/bin/env python3
"""Compatibility entrypoint for the evidence pin report tool."""
import importlib.util
import sys
import types
from pathlib import Path


def _main():
    package = Path(__file__).resolve().parents[1] / "evidence"
    evidence = types.ModuleType("evidence")
    evidence.__path__ = [str(package)]
    sys.modules.setdefault("evidence", evidence)
    spec = importlib.util.spec_from_file_location("evidence.pins", package / "pins.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evidence pin report tool")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(_main())
