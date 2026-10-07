#!/usr/bin/env python3
"""Check that imports between experiment areas follow the declared layering.

An area is a top-level directory; top-level scripts form the area ``(root)``.
A file may import its own area or any area in a strictly lower layer.  Imports
are read statically, so code embedded in strings passed to ``python -c`` and
modules loaded by path are not seen.
"""
import ast
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = '(root)'
# Lowest first.  Areas sharing a layer are peers and may not import each other.
LAYERS = (
    ('evidence',),
    ('insula',),
    ('dataset',),
    ('geometry',),
    ('camera',),
    ('segmentation',),
    ('detection',),
    ('range_view',),
    ('pipeline',),
    ('gpu', 'evaluation', 'tracking', 'association', 'inspection', 'motion-evaluation'),
    ('architecture',),
    ('tier1',),
    ('advanced',),
    ('cohort',),
    ('resources',),
    ('continuation',),
    ('continuation_control',),
    ('analysis', 'scripts', 'tests', 'tools', ROOT),
)
# Existing upward imports in sources whose bytes retained receipts cite.  Keep
# this list shrinking: a new entry needs the same justification as a new layer.
KNOWN_UPWARD = frozenset({('tier1/prepare_v3.py', 'cohort')})
UNLAYERED = frozenset({'research'})  # retained evidence, including frozen source copies


def sources(package=PACKAGE):
    package = Path(package)
    listed = git_sources(package)
    if listed is None:
        listed = filesystem_sources(package)
    return sorted(name for name in listed if name and (Path(package) / name).is_file()
                  and area(name) not in UNLAYERED)


def git_sources(package):
    try:
        return subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '--', '*.py'], cwd=package,
                              check=True, capture_output=True, text=True).stdout.split('\n')
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def filesystem_sources(package):
    names = []
    for path in Path(package).rglob('*.py'):
        relative = path.relative_to(package)
        if '__pycache__' in relative.parts:
            continue
        names.append(relative.as_posix())
    return names


def area(name):
    return name.split('/')[0] if '/' in name else ROOT


def imported_areas(name, tree, owners, areas):
    """Yield (line, module, areas that could provide it) for imports leaving the file's area."""
    here = area(name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        else:
            continue
        for module in modules:
            top = module.split('.')[0]
            if top in areas:
                found = {top}
            elif '.' in module or top in sys.stdlib_module_names:
                continue
            else:
                # A bare name resolves through sys.path, so only the areas
                # defining a module of that name can say where it leads.
                found = set(owners.get(top, ()))
                if here in found:
                    continue
            if found - {here}:
                yield node.lineno, module, found


def check(package=PACKAGE, layers=LAYERS, known=KNOWN_UPWARD, names=None):
    package = Path(package)
    rank = {name: index for index, group in enumerate(layers) for name in group}
    names = sources(package) if names is None else names
    owners = {}
    for name in names:
        owners.setdefault(Path(name).stem, set()).add(area(name))
    problems, used = [], set()
    for name in names:
        here = area(name)
        if here not in rank:
            problems.append(f'{name}: area {here!r} has no declared layer')
            continue
        tree = ast.parse((package / name).read_text(), filename=name)
        for line, module, found in imported_areas(name, tree, owners, set(rank) - {ROOT}):
            if len(found) > 1:
                problems.append(f'{name}:{line}: bare import {module!r} is provided by '
                                f'{sorted(found)}; qualify it with its area')
                continue
            target = found.pop()
            if rank.get(target, len(layers)) < rank[here]:
                continue
            if (name, target) in known:
                used.add((name, target))
                continue
            relation = 'peer' if rank.get(target) == rank[here] else 'higher'
            problems.append(f'{name}:{line}: imports {module!r} from {relation} area {target!r}')
    problems += [f'{name}: no longer imports {target!r}; remove it from KNOWN_UPWARD'
                 for name, target in sorted(known - used)]
    return problems


def main():
    problems = check()
    for problem in problems:
        print(problem)
    print(f'{"FAIL" if problems else "PASS"}: {len(problems)} layering problem(s) across {len(LAYERS)} layers')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
