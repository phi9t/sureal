#!/usr/bin/env python3
"""Report which tracked files retained receipts pin by SHA-256.

A file is pinned when the digest of its bytes appears anywhere in a tracked file
under research/.  Changing a pinned file leaves those receipts describing bytes
the working tree no longer holds, so a change should either leave pinned files
alone or be followed by re-admission of the affected receipts.

    pins.py status [PATH ...]   pinned/free counts per area, or details for PATHs
    pins.py check [--base REV]  pinned files a change modifies, deletes or renames
"""
import argparse
import collections
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from evidence.source_snapshot import file_sha256

PACKAGE = Path(__file__).resolve().parents[1]
EVIDENCE = 'research'
DIGEST = re.compile(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])')


def git(package, *arguments):
    return subprocess.run(['git', *arguments], cwd=package, check=True, capture_output=True).stdout


def repo_root(package):
    return Path(git(package, 'rev-parse', '--show-toplevel').decode().strip())


def package_relative_to_repo(package):
    root = repo_root(package)
    try:
        return Path(package).resolve().relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f'package is outside git repository: {package}') from error


def tracked(package, *patterns):
    return [name for name in git(package, 'ls-files', '-z', '--', *patterns).decode().split('\0') if name]


def citations(package=PACKAGE):
    """Map each digest named by retained evidence to the receipts naming it."""
    cited = collections.defaultdict(set)
    for name in tracked(package, EVIDENCE):
        path = Path(package) / name
        if path.is_file():
            for digest in set(DIGEST.findall(path.read_bytes())):
                cited[digest.decode()].add(name)
    return cited


def status(package=PACKAGE, cited=None):
    """Map each tracked non-evidence file to the receipts pinning its current bytes."""
    cited = citations(package) if cited is None else cited
    result = {}
    for name in tracked(package):
        path = Path(package) / name
        if not name.startswith(EVIDENCE + '/') and path.is_file():
            result[name] = sorted(cited.get(file_sha256(path), ()))
    return result


def changed(package=PACKAGE, base='HEAD', cited=None):
    """Map each file whose bytes at ``base`` are pinned and now differ to its receipts."""
    cited = citations(package) if cited is None else cited
    root = repo_root(package)
    package_relative = package_relative_to_repo(package)
    fields = git(
        root,
        'diff',
        '--name-status',
        '-M20%',
        '-z',
        base,
    ).decode().split('\0')
    if fields and fields[-1] == '':
        fields.pop()
    result = {}
    index = 0
    while index < len(fields):
        kind = fields[index]
        index += 1
        if not kind:
            continue
        if kind.startswith('R'):
            old_name = fields[index]
            new_name = fields[index + 1]
            index += 2
        else:
            old_name = fields[index]
            new_name = None
            index += 1
        if not (is_under(old_name, package_relative) or (new_name is not None and is_under(new_name, package_relative))):
            continue
        if kind[0] in 'MDR':
            receipts = cited.get(hashlib.sha256(git(root, 'show', f'{base}:{old_name}')).hexdigest())
            if receipts:
                result[describe_changed_path(old_name, new_name, package_relative)] = sorted(receipts)
    return result


def is_under(path, root):
    return root == '.' or path == root or path.startswith(root + '/')


def relative_to_package(path, root):
    if root == '.':
        return path
    if path == root:
        return '.'
    return path[len(root) + 1:]


def describe_changed_path(old_name, new_name, package_relative):
    old_in_package = is_under(old_name, package_relative)
    new_in_package = new_name is not None and is_under(new_name, package_relative)
    if new_name is None:
        return relative_to_package(old_name, package_relative) if old_in_package else old_name
    if old_in_package and new_in_package:
        return f'{relative_to_package(old_name, package_relative)} -> {relative_to_package(new_name, package_relative)}'
    return f'{old_name} -> {new_name}'


def describe(name, receipts):
    more = f' (+{len(receipts) - 3} more)' if len(receipts) > 3 else ''
    return f'{name}: pinned by {len(receipts)} receipt(s): {", ".join(receipts[:3])}{more}'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status').add_argument('paths', nargs='*')
    commands.add_parser('check').add_argument('--base', default='HEAD')
    arguments = parser.parse_args(argv)
    if arguments.command == 'check':
        found = changed(base=arguments.base)
        for name, receipts in sorted(found.items()):
            print(describe(name, receipts))
        print(f'{"FAIL" if found else "PASS"}: {len(found)} changed file(s) pinned by retained receipts')
        return 1 if found else 0
    files = status()
    if arguments.paths:
        for path in arguments.paths:
            name = Path(path).resolve().relative_to(PACKAGE).as_posix()
            if name not in files:
                print(f'{name}: not a tracked source file')
            elif files[name]:
                print(describe(name, files[name]))
            else:
                print(f'{name}: free (no retained receipt pins its current bytes)')
        return 0
    areas = collections.defaultdict(lambda: [0, 0])
    for name, receipts in files.items():
        areas[name.split('/')[0] if '/' in name else '(root)'][not receipts] += 1
    print(f'{"area":22s}{"pinned":>6s}{"free":>6s}')
    for name, (cited, free) in sorted(areas.items()):
        print(f'{name:22s}{cited:6d}{free:6d}')
    print(f'{"total":22s}{sum(a[0] for a in areas.values()):6d}{sum(a[1] for a in areas.values()):6d}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
