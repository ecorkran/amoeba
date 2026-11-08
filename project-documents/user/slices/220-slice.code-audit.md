---
docType: slice-design
slice: code-audit
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies: []
interfaces:
- 221-slice.the-cut
- 222-slice.store-config-and-set-up
- 223-slice.pause-handling
- 224-slice.status-and-decisions
dateCreated: 20261107
dateUpdated: 20261108
status: complete
---

# Slice Design: Code Audit

## Overview

The program-tool architecture (`220-arch.program-tool.md`) has a table of what it expects to stay and go, and calls it a guess. This slice replaces the guess with a decision for every piece of today's code. The output is one document, `user/analysis/220-analysis.code-audit.md`. No code changes.

## Value

Architectural enablement. 221 deletes from a list instead of re-reading the code, and 222 to 224 know what they can reuse.

## Scope

**Included:** the audit document, any Squadron issues it files, and a one-line note on any slice plan entry whose scope a verdict changes.

**Excluded:** changing code, tests, scripts or docs (221 deletes); designing the new schema or operations (222 to 224); editing the architecture (differences go in the audit); deleting or rebasing the slice 182 branch.

## The Audit Document

Frontmatter per `file-naming-conventions.md` for `analysis` (`topic: code-audit`). Sections, by name:

1. **Summary.** What stays, the 182 verdict, and any issues filed, in a few lines.
2. **Verdicts.** Tables for `src/amoeba`, `tests`, `scripts`, `docs` and packaged resources (`answering.yaml`, `slice_writing.yaml`, the schema directories, the console entry point). Each row: path, verdict, one-line reason.
3. **Dependencies of kept code.** For each `keep` or `rework` unit, what it relies on that is being deleted, and what replaces it. This includes coupling an import list wouldn't show: a question record's `node_id`, schema columns, references in `answering.yaml`, and answering code that is started by the tick rather than importing it. Nodes, journal entries, blocked states and the tick loop each appear here.
4. **Slice 182.** The verdict, and the branch's changed files sorted into take, rewrite or drop.
5. **Live tests.** Each file under `tests/live/answering/`: stays, waits on 223 (with the scenario A claim it covers), or delete.
6. **Move to Squadron.** Each item with its issue link.
7. **Differences from the architecture.** Each place the verdicts differ from the architecture's Current State table, with the reason.

## Decisions

### D1 — Granularity

A verdict goes at the coarsest level where everything inside agrees. A package that is all one verdict (`serve/`, `inbox/`, `feed/`) is one row. A mixed package is split by subpackage or module, which is expected for `store/`, `runner/` (especially `runner/answering/`), `process/`, `upstream/` and `program/`. Tests follow the code they exercise. A test of deleted code is deleted.

### D2 — Verdicts

| Verdict | Meaning |
|---|---|
| `keep` | Used unchanged by a scenario |
| `rework` | Kept, but changed to fit the new design |
| `squadron` | Useful to Squadron users in general; an issue is filed |
| `delete` | Removed in 221 |

Every reason names what the unit is for (scenario A, B, C or set-up) or says nothing uses it. A `keep` or `rework` with no scenario is not allowed. Judge by the scenarios, not by how good the code is: well-tested code that no scenario needs is deleted. Tests of kept code are `rework` only if their claim still holds without nodes, journal entries or the tick; otherwise they go, and 223 writes new ones.

### D3 — Replacements

Each entry in Dependencies of kept code names one replacement: a table or field in the new store (222), an operation (223 or 224), a value passed in by the caller, or nothing (dropped, with the reason). A replacement the architecture doesn't cover goes in Differences from the architecture and is not designed here.

### D4 — Slice 182

Read `git diff main...182-slice.program-concept-as-a-source` and sort each changed file:

- **Take:** works as-is on the new base. The architecture wants the program passage kinds and the concept read.
- **Rewrite:** the idea is wanted but the code is tied to deleted code, such as commit `e0a4615` passing the tick's program to the launch.
- **Drop:** the no-program path, which programs of one replace.

The verdict is merge (nothing it touches is deleted, which isn't expected), reuse parts, or redo. If it's reuse parts or redo, the 223 plan entry gets a note pointing to the Slice 182 section.

### D5 — Slice 180 and Squadron issues

Slice 180's slice-writing pipeline (`runner/request_run/`, `slice_writing.yaml` and its tests and fixtures) is expected to be `delete`, since scenarios A to C start no work. It is kept only if the audit names a scenario that calls it.

A unit is `squadron` only if Squadron users in general would want it, it can be described without mentioning Amoeba, and no open issue covers it (check `gh issue list -R ecorkran/squadron`; #299, #302, #303 and #304 already exist). Few or none are expected. Issues follow the style of #302 and #303.

## Integration Points

- **221:** the `delete` rows, the Dependencies section entries it must cut, and the Live tests verdicts.
- **222:** the verdicts under `store/`, `program/` and `cli/`, and the dependency entries whose replacement is the new store.
- **223:** the verdicts under `runner/answering/`, `upstream/`, and the `sq` launch, poll and resume code; the dependency entries whose replacement is a 223 operation; the Slice 182 take and rewrite groups.
- **224:** the verdicts on `inspection/` and the store's read views.

## Success Criteria

- The audit document exists with the seven sections above.
- Every package under `src/amoeba`, every test directory, `scripts/` and `docs/` is covered by a row with a verdict and a reason.
- Each kept unit's dependencies on deleted code are listed with a replacement, including nodes, journal entries, blocked states and the tick loop.
- Slice 182 has a verdict, with every changed file sorted.
- Every `squadron` row links an open issue.
- No file under `src/`, `tests/`, `scripts/` or `docs/` changes.

## Implementation Notes

Work on branch `220-slice.code-audit`. Do the answering and store code first, since the other verdicts follow from them. A person reads the audit to check it; there is no coverage script.
