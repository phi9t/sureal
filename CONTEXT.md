# Sureal collaboration language

These terms describe ownership and evidence for Sureal research work. Scientific task definitions retain their task-specific terminology.

## Language

**Task**: A stable research or engineering deliverable with an agreed goal, scope, dependencies and evidence-based acceptance. A task can have several execution attempts.
_Avoid_: Turn, session, experiment run as synonyms for a task.

**Admission**: The recorded decision that a pinned task definition, dependencies, scope, resources and verification contract permit execution.

**Attempt**: One admitted execution of a task under a specific brief, source base and current owner. Its history remains attributable after repair, handoff or replacement.
_Avoid_: Turn, thread or process as synonyms for an attempt.

**Worker seat**: One unit of concurrent task-attempt capacity, occupied until the attempt's effects and retained work are safely reconciled.

**Claim**: The current operational ownership of a task, bound to a particular attempt and generation.

**Candidate**: An immutable proposed task result, identified by exact content and its admitted execution context.
_Avoid_: Branch name as a synonym for candidate identity.

**Landing**: The observed integration of the exact accepted candidate into the authoritative mainline. Publication, retention and cleanup are separate outcomes.

**Closure**: An evidence-backed determination that every applicable acceptance and integration obligation of a task is satisfied.
_Avoid_: Goal completion, process exit or queue label as synonyms for closure.

**Stale attempt**: An attempt whose admitted source base or acceptance context no longer matches what would permit its candidate to land.

**Progress incident**: An evidence-linked concern about goal progress or execution responsiveness, separate from ownership and acceptance.
