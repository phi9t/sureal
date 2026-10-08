# Dev research journal: the semantic-layout effort

How the spec, the tickets and the traecli worker sessions were put together, what happened when they ran, and what was learned. Written 2026-10-05 by the lead session, mid-effort (16 of 28 tickets merged). Entries are dated; the mechanism sections describe the current state and note when something changed.

## 1. From a deep dive to a decided design

**04:00 to 05:40 UTC.** The effort began as "deep dive and improve the codebase architecture" on `experiments/waymo-perception`. The deep dive found that 652 of 694 tracked files had the SHA-256 of their current bytes recorded in retained receipts under `research/`, and that two validators required an exact file inventory of five directories. Everything was frozen in place, which explained the `_v2`/`_v3` copies, the 91 `sys.path` insertions and the 61 copies of a file-digest helper. The first deliverable was therefore not a refactor but three checks (`tools/layers.py`, `tools/pins.py`, `tools/suites.py`) and a map, because any refactor would strand evidence.

The design was then settled by interview (the `grilling` skill): 23 numbered questions over six rounds, each with a recommendation, answered one round at a time. Two background agents supplied facts in parallel (which checks compare receipts against the working tree; how the sibling repos run Bazel under Insula) so the questions never asked the owner for something that could be looked up. The decisions became three ADRs (`docs/adr/0001`, `docs/adr/0002`, the autonomy ADR on source pins), two glossary terms (**source pin**, **source snapshot**) and the verbatim layout standard at `docs/repo-structure.md`.

The owner overrode three recommendations on the way: Bazel runs *inside* Insula rather than beside it; the move to `autonomy/` happens in one rename rather than staged around the frozen sweep; and the curriculum is named `parallax/`, not `reconstruction/`.

## 2. The spec

`spec.md` was synthesized from the conversation, not by further interview. Its shape:

- a problem statement from the contributor's point of view (four concrete costs of the frozen tree);
- 49 user stories in five groups (layout, build and test, evidence, re-admission, migration safety);
- implementation decisions without file paths, including an explicit order of work;
- testing decisions naming three seams, highest first: the wrapper running Bazel, the evidence module's interface with a local store standing in for HDFS, and the wrapper's printed sandbox command;
- a measured baseline the whole effort is held to: 176 test modules, 140 passing, 34 unavailable outside a rootfs, 2 failing;
- an out-of-scope list and a notes section for known risks (the curriculum's Python 3.10 contract; whether Bazel's sandbox works nested inside Insula).

One amendment so far: at ticket 13 the Python import root was changed from the repository root to `autonomy/`, because live gates mount the component directory as `/experiment` and every existing caller already imports from there.

## 3. The tickets

27 tickets were cut from the spec (28 after a follow-up ticket was added), one Markdown file each under `issues/NN-slug.md`, numbered in dependency order. Each file has four parts: **What to build** (end-to-end behaviour, not layers), **Blocked by** (ticket numbers with titles, or "None"), **Status** (`ready-for-agent`, `ready-for-human`, `done`, `needs-info`) and acceptance criteria as checkboxes.

The shape of the graph:

- a chain for the foundation (rootfs with Bazel, wrapper, all tests as targets, GPU rootfs), with the curriculum track (05, 06) branching off after the wrapper;
- the two renames and the docs ticket;
- the evidence model (module, HDFS store, two consumers) before any reorganisation, so that moving pinned files stops stranding evidence;
- the concept reorganisation as expand–contract batches (13 to 25), lowest layer first, with a final contract ticket (26) and the re-admission (27).

Two tickets were labelled `ready-for-human` (HDFS credentials; an admission decision with a GPU gate). Ticket 28 was added mid-effort to collect review follow-ups (real `git`, `curl`, pytest and a C++ compiler in the rootfs; Bazel caches off `/outputs`), and tickets 20 and 21 were re-blocked on it because they need the compiler.

## 4. The worker mechanism

One coordinator, `workstream.py` (about 200 lines, standard library), with five commands: `status`, `frontier`, `up`, `launch NN...`, `merge NN`.

**Roles.** The lead is one interactive Claude Code session, the only role the owner talks to. Workers are interactive traecli TUI sessions, GPT-5.5 at xhigh reasoning with `--yolo` (no approvals, no sandbox), one per ticket. There is no supervisor; the boundary is instructions plus the lead's after-the-fact verification.

**Isolation.** `launch` creates `.worktrees/semantic-layout-NN-slug` on branch `work/semantic-layout/NN-slug` from the integration branch, so a ticket always starts with its blockers' work. Finished branches merge with `--no-ff` into `work/semantic-layout/integration`, never into `phi9t/mainline`, because other agents commit there and landing is the owner's call.

**Visibility.** Everything runs in tmux session `vision-frontier-workstream`: a `status` window looping the ticket table every 30 seconds, a `dashboard` window on the shared `traecli app-server` daemon, and one window per ticket named `NN-slug`, kept open after traecli exits.

**The launch.** Exactly: `traecli -m gpt-5.5 -c model_reasoning_effort=xhigh -c model_reasoning_summary=detailed --yolo "$(cat prompt.md)"` with the worktree as cwd. The prompt (the `PROMPT` constant in the coordinator; a rendered copy per ticket under `~/.cache/sureal/workstream/semantic-layout/NN-slug/`) gives a read order (agent guide, ADRs, standard, spec, ticket), the scope (that ticket only), the boundaries, the method (test-first at the spec's seams), the gates, and the reporting protocol.

**The channel.** No messages pass between lead and worker in the normal case. The worker ticks criteria in its ticket file and commits; when everything is verified it writes a `## Comments` section with what it built and the exact verification commands and results, commits, then sets `Status: done` in a separate final commit. If stuck it writes the question and sets `needs-info`. The coordinator reads the ticket file in the worker's worktree for live state and the copy on the integration branch for whether a ticket is finished.

**Waking the lead.** A background shell loop polls `workstream.py status` until the ticket leaves `running` and the worktree is clean, then exits, which re-invokes the lead. Nothing else wakes it.

**Review and merge.** On wake, the lead reads the ticket's comments and the diff, re-runs the gates itself in the worker's tree, checks shared external state against a baseline recorded before launch, and either merges or writes `review-N.md` into the ticket's state directory and sends the worker one line in its tmux window pointing at it. Review rounds so far: tickets 02, 03, 04, 09, 12, 28 one round each; ticket 13 two rounds. The lead edits a worker's branch itself only for one-file corrections (ticket 14's layout test) and records that in the ticket.

**Hand-offs between tickets.** The integration branch's ticket files are the ledger: the lead appends corrections and follow-up criteria there (ticket 06 received two criteria from ticket 05's review; ticket 07 received a corrected pin record).

## 5. What happened, in order

| When (UTC) | Event |
| --- | --- |
| 05:43 | Ticket 01 launched: a new CPU rootfs with Bazel 9.2. About 10 minutes to a verified merge. |
| 05:53 | First race: the worker set `done` before committing. Watcher now waits for a clean tree; prompt now says commit first, then `done`. |
| 07:07 | Ticket 02 sent back: it had turned Bzlmod off and committed an empty lock, used a hand-written test rule instead of `rules_python`, put the whole experiment on `PYTHONPATH`, and left 3.5 GB of probe caches. The lead's own check showed Bzlmod worked in 5 seconds. Settled: batch server mode and the standalone spawn strategy are needed inside the sandbox. |
| 07:55 to 08:20 | Tickets 03, 05, 06. Ticket 03 was sent back for a fake `git`, a fake `curl` and a home-made pytest that made excluded tests "pass"; it came back with honest tags and a baseline reconciliation table. Ticket 05 gave the curriculum its own rootfs. Ticket 06 was the first pure-rename move. |
| 08:36 to 17:26 | Ticket 04 verified (24 torch tests under `--config=cuda`), then stuck for eight hours: the lead's hand-back message was typed into the worker's input box but the Enter keypress never registered. Found when the owner asked for status. Every hand-back now confirms the worker started. Ticket 04 also left five 13 GB rootfs builds behind; the lead deleted four. |
| 18:17 | Ticket 07: 2,987 pure renames, then path edits. The pin report under-reported (0 instead of 34 pinned files changed) because it compared paths inside the package across a rename; corrected in the ticket record. The worker's own review pass reopened the ticket once to fix a harness path. |
| 18:57 to 19:58 | Tickets 08 to 12. Ticket 09 sent back once: the snapshot digest was taken over gzip output, which differs between the host's zlib-ng and the rootfs's zlib. Ticket 12 sent back once: receipts named Bazel targets that did not exist. |
| 19:0x | `/tmp` found at 100% of inodes (not bytes), the cause of intermittent "no space left on device". 20,855 stale test directories from another project, older than 48 hours, deleted; other projects' live entries left alone. |
| 20:25 | Ticket 28 merged: real tools in the rootfs; default run 139 → 147; placeholder C++ toolchain gone. |
| 22:01 | Ticket 13, the first concept batch, after two rounds: loose files became `py_library` targets, layout tests were removed, the wrapper's fake-package import became a plain path insertion, the pin report learned to follow renames, and a stale documentation link was fixed. |
| 22:40, 23:03 | Tickets 15 and 14 merged, 14 after the worker merged 15 underneath itself. First parallel concept batches. |

## 6. What the mechanism got right

- **The ticket file as the only channel.** Workers reported progress, verification commands and results in a form the lead could re-run. Every merge decision was made on the lead's own re-run of the gates, not the worker's claim; the claims held every time they were checked.
- **Worktree per ticket from the integration branch.** No worker ever touched another's tree or mainline.
- **Blocking edges as the launch rule.** Parallelism fell out of the graph without planning: 03∥05, 08∥09, 10∥11∥12∥28, 16∥18∥22.
- **Review as a written file plus one line in tmux.** The worker reads the review in its own context; the owner can read the same file. Seven of 28 tickets needed a round; the rounds were about substance (fake tools, non-deterministic digests, unresolvable labels), not style.
- **Explicit rules learned from failures were added to the prompt the same day**: commit before `done`; meet spec requirements or stop with `needs-info`; keep one cache; the five gates; the concept conventions; merge integration before final verification.

## 7. What it got wrong or still lacks

- **No supervision.** A `--yolo` worker with full access built images next to shared caches with nothing but a prompt and a baseline diff between it and the originals. It also cost 52 GB of forgotten builds before the rule "delete your own failed builds" existed.
- **A done signal that can race the commit** (fixed by convention, not mechanism).
- **A hand-back that can silently fail to send** (eight hours lost; now checked, still not mechanised).
- **Progress columns that read zero until the end**, because workers commit late despite being asked to commit incrementally.
- **No event stream, cost, token or wall-clock limit.** The only record of a worker's reasoning is its tmux scrollback and the traecli session.
- **The lead's verification is itself fallible.** Ticket 13's first submission had a failing documentation gate that the lead missed by reading the test count line instead of the result line.
- **The coordinator has no tests**, and the pin report's rename blind spot was only found after it had misled once.

The Corenius repository's `tools/agents/` toolbox addresses most of the first five (supervise with verdicts, gated landing, claim sampling, tracked claims) and is the intended successor; the owner's instruction is to prove it there first. A case study built from this effort's notes was landed in Corenius as `docs/practice/imported/sureal-semantic-layout.md`.

## 8. Numbers so far

- 28 tickets: 16 merged, 3 running, 9 waiting. 7 tickets needed one review round, 1 needed two.
- Test gates on the integration branch: 149 default perception tests, 24 torch tests under `--config=cuda`, 17 curriculum tests, 30 publication-audit tests; one perception module excluded (needs `protoc` and upstream sources).
- Rootfs versions built: perception CPU v3 and v4, perception GPU v6, curriculum v1 and v2. Originals untouched, verified by lock digest.
- Pinned files changed by the migration so far: 34 (rename), 23 (sustained guards), 86 (insula/evidence), 28 (geometry), 65 (dataset). Each is recorded in its ticket; all are the cost the ADR accepted.
