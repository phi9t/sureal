#!/usr/bin/env python3
"""Coordinate ticket workers for this effort.

Each ticket is worked by one traecli session in its own git worktree, shown as
a window of the tmux session below.  The integration branch is the source of
truth for which tickets are finished: a ticket is *merged* when its file on
that branch says ``Status: done``.

    workstream.py status          one line per ticket
    workstream.py frontier        tickets that can start now
    workstream.py up              start the app-server daemon, dashboard and status windows
    workstream.py launch NN ...   create the worktree and start a worker for each ticket
    workstream.py merge NN        merge a finished ticket branch into the integration branch
"""
import argparse
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

EFFORT = Path(__file__).resolve().parent
REPO = EFFORT.parents[1]
SESSION = 'vision-frontier-workstream'
INTEGRATION = f'work/{EFFORT.name}/integration'
WORKER = ['traecli', '-m', 'gpt-5.5', '-c', 'model_reasoning_effort=xhigh',
          '-c', 'model_reasoning_summary=detailed', '--yolo']
STATE = Path.home() / '.cache/sureal/workstream' / EFFORT.name
OPEN = {'ready-for-agent', 'ready-for-human'}


def run(*command, cwd=REPO, check=True):
    return subprocess.run(command, cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


def worktree(name):
    return REPO / '.worktrees' / f'{EFFORT.name}-{name}'


def integration():
    """Return the integration worktree, creating the branch from the current one on first use."""
    path = worktree('integration')
    if not path.exists():
        run('git', 'worktree', 'add', '-b', INTEGRATION, str(path), 'HEAD')
    return path


def parse(path):
    text = path.read_text()
    field = lambda label: re.search(rf'\*\*{label}:\*\* (.*)', text).group(1)
    boxes = re.findall(r'^- \[([ x])\]', text, re.M)
    return {'number': path.name[:2], 'slug': path.stem[3:], 'title': text.splitlines()[0].split(': ', 1)[1],
            'status': field('Status').strip(), 'blocked': re.findall(r'(\d\d) \(', field('Blocked by')),
            'checked': boxes.count('x'), 'boxes': len(boxes)}


def tickets():
    """Describe every ticket, reading its live state from its own worktree when it has one."""
    issues = (integration() / EFFORT.relative_to(REPO) / 'issues')
    merged = {p.name[:2]: parse(p) for p in sorted(issues.glob('*.md'))}
    windows = set(run('tmux', 'list-windows', '-t', SESSION, '-F', '#{window_name}', check=False).split())
    result = []
    for number, base in merged.items():
        name = f'{number}-{base["slug"]}'
        tree = worktree(name)
        live = parse(tree / EFFORT.relative_to(REPO) / 'issues' / f'{name}.md') if tree.exists() else base
        ready = all(merged[b]['status'] == 'done' for b in base['blocked'])
        if base['status'] == 'done':
            state = 'merged'
        elif tree.exists():
            state = live['status'] if live['status'] not in OPEN else ('running' if name in windows else 'stopped')
        else:
            state = 'ready' if ready else 'blocked'
        commits = run('git', 'rev-list', '--count', f'{INTEGRATION}..HEAD', cwd=tree) if tree.exists() else ''
        last = run('git', 'log', '-1', '--format=%cr', cwd=tree) if commits not in ('', '0') else ''
        result.append({**live, 'name': name, 'state': state, 'tree': tree, 'commits': commits, 'last': last,
                       'human': base['status'] == 'ready-for-human'})
    return result


def status(_):
    print(f'{"ticket":44s}{"state":12s}{"criteria":>9s}{"commits":>8s}  last commit')
    for t in tickets():
        blocked = f'  (waits for {", ".join(t["blocked"])})' if t['state'] == 'blocked' else ''
        print(f'{t["name"][:43]:44s}{t["state"]:12s}{t["checked"]:>5d}/{t["boxes"]:<3d}{t["commits"]:>8s}  '
              f'{t["last"]}{blocked}{"  [human]" if t["human"] and t["state"] != "merged" else ""}')


def frontier(_):
    for t in tickets():
        if t['state'] == 'ready':
            print(t['number'], t['title'], '[human]' if t['human'] else '')


def tmux_window(name, command, cwd):
    exists = subprocess.run(['tmux', 'has-session', '-t', SESSION], capture_output=True).returncode == 0
    start = ['new-window', '-d', '-t', f'{SESSION}:'] if exists else ['new-session', '-d', '-s', SESSION]
    run('tmux', *start, '-n', name, '-c', str(cwd), command)


def up(_):
    integration()
    print(run('traecli', 'app-server', 'daemon', 'start', check=False))
    windows = run('tmux', 'list-windows', '-t', SESSION, '-F', '#{window_name}', check=False).split()
    script = shlex.quote(str(Path(__file__).resolve()))
    if 'status' not in windows:
        tmux_window('status', f'while true; do clear; date; python3 {script} status; sleep 30; done', REPO)
    if 'dashboard' not in windows:
        tmux_window('dashboard', 'traecli dashboard; exec zsh', REPO)


PROMPT = '''You are implementing one ticket of the "{effort}" effort in this git worktree.

Read these first, in order:
1. AGENTS.md and the files it points to under docs/agents/
2. docs/adr/ (both ADRs), autonomy/docs/adr/, and docs/repo-structure.md
3. .scratch/{effort}/spec.md
4. Your ticket: .scratch/{effort}/issues/{name}.md

Your job is that ticket and nothing else: make every acceptance criterion true and verified.

Rules:
- Work only inside this worktree ({tree}) on its branch ({branch}). Never touch the main checkout or
  another worktree, never push, never merge, never rewrite history.
- Shared state outside the repository (for example ~/.cache/waystone) is used by other work. You may
  create new versioned paths there. Never modify, move or delete anything that already exists there.
- Files under any research/ directory are retained evidence. Never modify them.
- Do not add, change or remove any .py file under
  autonomy/{{pipeline,gpu,tier1,cohort,resources}} unless your ticket requires it; a
  running guard validates their exact inventory. Run
  `python3 autonomy/tools/pins.py check --base {integration}` before each commit
  and record in the ticket which pinned files you changed and why.
- Work test-first at the seams the spec names. Run the narrowest relevant tests as you go and the
  full relevant suite at the end. Report failures honestly; never weaken a check to make it pass.
- Commit in small steps on this branch with clear messages.

Keeping the ticket current (this is how progress is monitored):
- Tick each acceptance criterion in your ticket file (`- [x]`) as soon as it is verified, and commit.
- When every criterion is ticked, append a `## Comments` section with what you built, the exact
  verification commands and their results, and anything a reviewer must know, and commit. Only
  then, in a final separate commit, set the ticket's status line to `**Status:** done`, and stop.
  Never write `done` while the tree has uncommitted changes.
- The lead reviews your branch against the spec and ADRs before merging. Where the spec or an ADR
  states a requirement (for example Bzlmod, `rules_python` with the rootfs interpreter, no
  `PYTHONPATH` in the sandbox), meet it; if it cannot be met, stop with `needs-info` and the exact
  error instead of substituting something else.
- Run Bazel only through `./bazelw`. Keep one cache layout under `.bazel-cache/` in this worktree
  and delete any extra probe caches you create; the disk is nearly full.
- If you cannot proceed without a decision or access you do not have, append the question under
  `## Comments`, set the status line to `**Status:** needs-info`, commit, and stop.
'''


def launch(arguments):
    known = {t['number']: t for t in tickets()}
    for number in arguments.numbers:
        t = known[number]
        if t['state'] != 'ready':
            sys.exit(f'{t["name"]} is {t["state"]}, not ready')
        branch = f'work/{EFFORT.name}/{t["name"]}'
        run('git', 'worktree', 'add', '-b', branch, str(t['tree']), INTEGRATION)
        directory = STATE / t['name']
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'prompt.md').write_text(PROMPT.format(effort=EFFORT.name, name=t['name'], tree=t['tree'],
                                                           branch=branch, integration=INTEGRATION))
        command = f'{shlex.join(WORKER)} "$(cat {shlex.quote(str(directory / "prompt.md"))})"; exec zsh'
        tmux_window(t['name'], command, t['tree'])
        print(f'launched {t["name"]} in tmux {SESSION}:{t["name"]} at {t["tree"]}')
        time.sleep(2)


def merge(arguments):
    t = {t['number']: t for t in tickets()}[arguments.number]
    if t['state'] != 'done':
        sys.exit(f'{t["name"]} is {t["state"]}, not done')
    if run('git', 'status', '--porcelain', cwd=t['tree']):
        sys.exit(f'{t["name"]} has uncommitted changes')
    print(run('git', 'merge', '--no-ff', '-m', f'Merge ticket {t["number"]}: {t["title"]}',
              f'work/{EFFORT.name}/{t["name"]}', cwd=integration()))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for name, function in (('status', status), ('frontier', frontier), ('up', up)):
        commands.add_parser(name).set_defaults(function=function)
    launcher = commands.add_parser('launch')
    launcher.add_argument('numbers', nargs='+')
    launcher.set_defaults(function=launch)
    merger = commands.add_parser('merge')
    merger.add_argument('number')
    merger.set_defaults(function=merge)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == '__main__':
    main()
