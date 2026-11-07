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
dateUpdated: 20261107
status: not_started
turns: 12
promptTokens: 650831
cachedTokens: 591027
cacheWriteTokens: 59780
completionTokens: 12774
durationSeconds: 134.9
costUsd: 0.852354
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 0.8523540000000001
    completionTokens: 12774
---

# Slice Design: Code Audit

## Overview

Amoeba's code was built for a resident supervisor that the program-tool architecture (`220-arch.program-tool.md`) replaces. That architecture has a table of what it expects to stay and go, and it calls the table a guess. This slice replaces the guess with a decision for every piece. The output is one analysis document, `user/analysis/220-analysis.code-audit.md`. It sorts every unit of `src/amoeba`, the tests, the scripts and the docs into keep, keep and rework, move to Squadron, or delete. For each kept unit it lists what that unit depends on that is being deleted, and what replaces each dependency. It also gives a verdict on slice 182's parked branch and confirms the delete of slice 180's slice-writing pipeline.

The slice changes no code. Its other outputs are any Squadron issues the audit files and a one-line note on any slice plan entry whose scope a verdict changes.

## Value

Architectural enablement. Slices 221 to 224 start from a decided list instead of re-reading the code (see Provides to Other Slices). The PM gets one document showing what survives, and why.

## Technical Scope

**Included:**

- The audit document in Component Structure, any Squadron issues it files (D6), and any one-line slice plan notes (State Management).

**Excluded:**

- Any change to code, tests, scripts or docs. Deletion happens in 221.
- Designing the new schema or the operations. The audit says what can be reused. Slices 222 to 224 design what is built from it.
- Editing the architecture document. Differences go in the audit's own section.
- Deleting or rebasing the slice 182 branch. Branches are deleted only on instruction.

## Dependencies

### Prerequisites

- None among slices. The audit reads the code as it stands on `main`, and the slice 182 branch `182-slice.program-concept-as-a-source`.
- `gh` access to `ecorkran/squadron`, needed only if an issue is filed.

### Interfaces Required

- `220-arch.program-tool.md`: the scenarios, the eight operations, and the Current State table the audit settles.
- `user/notes/005-usage-scenarios.amoeba.md` and `user/project-guides/000-concept.amoeba.md`: what scenarios A, B and C mean when a reason cites one.
- Squadron's open issues `#299`, `#302`, `#303` and `#304`, so that a move-to-Squadron verdict does not duplicate one of them.

## Architecture

### Component Structure

The audit document has these sections, in this order:

1. **Summary**: the 182 verdict in one line; the count of Squadron issues filed.
2. **Source verdicts**: one table per top-level package under `src/amoeba`, at the granularity D1 sets.
3. **Test verdicts**: one table per test directory. Top-level `tests/*.py` files and shared harnesses are grouped by filename-prefix rows (D1).
4. **Other files**: `scripts/`, `docs/`, packaged resources (`answering.yaml`, `slice_writing.yaml`, `store/schema/`, `store/program_schema/`), and the console entry point.
5. **Dependencies of kept code**, in two parts (D3, D4):
   - 5a, **import coupling**: produced by the scan, and reproducible.
   - 5b, **non-import coupling**: read by hand. Covers fields, columns, foreign keys, schema, YAML references and call direction.
6. **Slice 182**: the verdict, with the files sorted into take, rewrite or drop (D5).
7. **Slice 180 pipeline**: the confirmation or the reversal (D7).
8. **Live tests**: D8's word for each file, in its own column, not as a D2 verdict.
9. **Move to Squadron**: each item with its issue link, or its reason for becoming a delete (D6).
10. **Differences from the architecture**: each row where the verdict differs from the architecture's Current State table, with the reason.
11. **Import scan**: the exact 5a scan command (D3).

Only rows in sections 2 to 4 start with a repo path. Tables in sections 5 to 10 put any path in a later column, so they never count as verdict rows.

### State Management

The slice keeps no runtime state. Its persistent output is the analysis document, which moves from `not_started` to `complete`. If a verdict changes the scope of another slice, that slice's plan entry gets a one-line note. The likely case is 182 being redone inside 223.

## Technical Decisions

### D1 — Unit of verdict
Status: decided

The audit gives a verdict at the coarsest level where everything inside shares one verdict, and goes deeper only where the contents split:

- A whole package gets one verdict when all of it shares one, for example `serve/`, `inbox/` and `feed/`.
- A mixed package gets one verdict per subpackage, and per module where a subpackage is itself mixed. This is expected for `store/`, `runner/` (including `runner/answering/`), `process/`, `upstream/`, `cli/`, `inspection/` and `program/`.
- Tests follow the same rule. Top-level `tests/*.py` files and shared harnesses (`*_harness.py`, `*_stub*.py`, `conftest.py`, `fixtures/` subdirectories) are grouped by filename-prefix rows, such as `tests/test_observer_sq` for the `test_observer_sq_*.py` files. Files that exercise one unit but share no prefix each get their own row.

Every verdict row is a table row whose first cell is the unit's repo-relative path in backticks, for example `src/amoeba/runner/answering/passages.py`. A directory row's path ends in `/`; a filename-prefix row does not. No path has two rows. A file's verdict is the verdict of the longest row path that is a prefix of the file's path. That lets a module row override its package row, and it lets the walkthrough's coverage check map every file to a verdict.

Rejected: package-level only, which hides the split inside `runner/answering/` and `store/` that 221 and 222 depend on. Module-level everywhere, which produces several hundred rows of deletes that say nothing new.

### D2 — Verdict vocabulary and reasons
Status: decided

There are four verdicts, written exactly as follows so the tables can be filtered:

| Verdict | Meaning |
|---|---|
| `keep` | Used unchanged by a scenario |
| `rework` | Kept, but changed to fit the new design (re-keyed, loses its dependencies on deleted code, launching rewritten). |
| `squadron` | Useful to Squadron users in general. A Squadron issue is filed (D6) |
| `delete` | Removed in 221 |

The reason fits on one line and names what the unit is for: `A`, `B`, `C` or `set-up`, or `none` when no scenario uses it. A `keep` or `rework` row with the reason `none` is invalid.

### D3 — How the dependencies of kept code are found
Status: decided

Section 5 has two parts, because a scan of imports can find only some of the coupling.

**5a, import coupling (scanned).** After the verdicts are set, an AST scan lists each `amoeba.*` import that resolves to a `delete` unit. It covers every `keep` and `rework` `.py` file under `src/amoeba`, `tests` and `scripts`, which includes the console entry point module. It includes imports inside functions and `TYPE_CHECKING` blocks, and it resolves relative imports.

An imported name is resolved to the module that defines it. For `from amoeba.store import X`, the scan follows `X` through the package `__init__` re-exports to its defining submodule, and judges that submodule's verdict, not the package's. An `amoeba.*` import that the scan cannot resolve to a single kept unit is printed as a hit. That covers a bare `import amoeba.<pkg>` of a mixed package, and, after the cut, an import of a module that no longer exists. So empty output means every import resolved to a kept unit. The scan reads verdicts from the section 2 to 4 tables by the D1 longest-prefix rule, so after the cut it has the same input. Resolving re-exports is needed because `amoeba.store` re-exports its submodules' names through its `__init__`.

The command goes in section 11 and is not committed as code. 5a is the only part that is reproducible: rerunning the command gives exactly 5a. 221 runs the same command after the cut, and it must print nothing. 221 may turn that into a rule in `test_import_boundaries.py`. That choice belongs to 221.

**5b, non-import coupling (read by hand).** This covers coupling an import scan cannot see:

- fields and foreign keys, for example a question record's `node_id`
- SQL schema and column references
- YAML references in `answering.yaml`
- call direction, for example answering code that is started by the tick rather than importing it

Nodes, journal entries, blocked states and the tick loop must each appear in 5a or 5b.

Rejected: grep on `from amoeba.`, which misses relative imports and re-exports.

### D4 — What replaces each deleted dependency
Status: decided

Each row in 5a and 5b names one replacement, from this set:

- **New store (222)**: the table or field that takes over, for example a question keyed on run id and `paused_at` instead of a node id.
- **Operation (223 or 224)**: the operation that now does the work, for example `handle_pause` launching and waiting instead of the tick loop.
- **Parameter**: the value is passed in by the caller instead of read from deleted state.
- **Dropped**: the use goes away with nothing in its place, with the reason.

A replacement that the architecture does not cover is flagged in section 10, not designed in the audit.

### D5 — Slice 182 verdict
Status: decided

The audit reads `git diff main...182-slice.program-concept-as-a-source` (about 2.3k lines added across 28 files) and sorts each changed file into one of three groups:

- **Take**: works as-is on the new base. The architecture wants the program passage kinds and the concept read.
- **Rewrite**: the idea is wanted but the code is tied to deleted code. Commit `e0a4615` passes the tick's program to the launch, so the tick goes and this needs rewriting.
- **Drop**: the no-program path. Programs of one replace it.

The verdict follows from that sorting:

- **merge** when nothing touched by the branch is deleted.
- **reuse parts** when the take group includes the program passage kinds module. 223 picks up the take group from the branch.
- **redo** otherwise.

Whatever the verdict word, section 6 still lists every takeable file, so a redo verdict doesn't hide reusable files from 223.

Because the branch is built on the tick and on the no-program path, merging is not expected. If the verdict is reuse parts or redo, the 223 slice plan entry gets a note pointing to the audit section.

### D6 — Move to Squadron and filing issues
Status: decided

A unit is marked `squadron` only when Squadron users in general would want it, it can be described without mentioning Amoeba, and no open issue already covers it. Before filing, check `gh issue list -R ecorkran/squadron`. A unit already covered by `#299`, `#302`, `#303` or `#304` gets a `delete` verdict with that issue cited as the reason. Few or no units are expected here.

The slice plan's success criteria authorize filing the issues. Each issue follows the style of `#302` and `#303`: the behavior wanted, why a general user would want it, and no mention of Amoeba.

### D7 — Slice 180 slice-writing pipeline
Status: decided

The expected verdict is `delete`, because scenarios A to C start no work and the architecture retires requests. The scope is `src/amoeba/runner/request_run/` (including `slice_writing.yaml`), `tests/runner/request_run/`, `tests/live/request_run/`, `tests/fixtures/slice_writing/` and `tests/test_probes_request_run.py`, plus any harness used only by those. The verdict is reversed only if the audit finds a scenario that calls it, and the scenario must be named.

### D8 — Live answering tests
Status: decided

Each file under `tests/live/answering/` gets one of three verdicts:

- **stays**: runs against the kept pipeline with no store or tick. This feeds 221's criterion that the live answering tests still pass.
- **waits on 223**: needs `handle_pause` or the new question record, with the reason.
- **delete**.

The architecture names these tests as the scenario A check. The audit lists which of them carry that role.

### Patterns and Conventions

- Frontmatter follows `file-naming-conventions.md` for `analysis`: `docType: analysis`, `project: amoeba`, `topic: code-audit`, the dates, and `status`.
- Verdict words are exactly those in D2. Paths are repo-relative and in backticks.
- Scenario labels are exactly `A`, `B`, `C`, `set-up` and `none`.
- Where a verdict differs from the architecture's Current State table, the audit records it in section 10 and leaves the architecture alone. The audit replaces that table for 221 to 224.

## Integration Points

### Provides to Other Slices

- **221**: the delete list, which is every `delete` row across sections 2 to 4. Also the 5a scan command and its expected empty result after the cut, and the list of live tests that may wait on 223.
- **222**: the `keep` and `rework` rows under `src/amoeba/store/` and `src/amoeba/program/`. These include the question and program code to re-key. Also the section 5 rows whose replacement is the new store, and the verdicts on `src/amoeba/cli/` and the `amoeba` console entry point, which decide whether the CLI that 222 to 224 build on is reused or replaced.
- **223**:
  - the `keep` and `rework` rows under `src/amoeba/runner/answering/` and `src/amoeba/upstream/`
  - the verdicts on the Squadron-output readers in `src/amoeba/process/` and on the `sq`-invocation and polling code in `src/amoeba/runner/` (launch, observe, resume). The audit names each of these, whether kept or deleted, because 223's resume path starts from them.
  - the section 5 rows whose replacement is a 223 operation
  - the 182 take and rewrite groups
- **224**: the verdicts on `src/amoeba/inspection/` and on the store's read views. The architecture expects `status` and `decisions` to mostly replace these, so these verdicts tell 224 what it can reuse.

### Consumes from Other Slices

- **Slices 140–144 and 181** (complete): the code being judged.
- **Slice 182 branch** (parked): read only, never merged or changed by this slice.

## Success Criteria

### Functional Requirements

- `user/analysis/220-analysis.code-audit.md` exists with valid `analysis` frontmatter and the eleven sections in Component Structure.
- Every file under `src/amoeba`, `tests` and `scripts` (excluding `__pycache__`), and every entry in `docs/`, maps to a row by the D1 longest-prefix rule, and no path has two rows. Each row has one D2 verdict and a reason naming a scenario or `none`.
- No `keep` or `rework` row has the reason `none`.
- 5a lists every import the D3 scan finds from kept code into deleted code. 5b lists the non-import coupling. Every row in both parts has a D4 replacement. Nodes, journal entries, blocked states and the tick loop each appear in 5a or 5b.
- Section 6 gives the 182 verdict (merge, reuse parts or redo), with each changed file in take, rewrite or drop.
- Section 7 confirms or reverses the delete of the slice 180 pipeline, naming the paths.
- Every `squadron` row links an issue filed on `ecorkran/squadron`, or has been changed to `delete` with the reason.

### Technical Requirements

- No files under `src/`, `tests/`, `scripts/` or `docs/` change in this slice.
- The section 11 command runs as written from the repo root. The 5a scan reproduces 5a exactly.

### Integration Requirements

- 221's design can take its delete list directly from the audit, without opening the code to decide anything.
- If the 182 verdict is reuse parts or redo, the 223 slice plan entry notes it.

### Verification Walkthrough

These are run from the repo root after the audit is written. `AUDIT=project-documents/user/analysis/220-analysis.code-audit.md`.

1. **Every file is covered, and no path has two rows.** Both commands should print nothing. Only the first cell of each table row counts as a row path, so a path mentioned in prose does not count as coverage.
   ```bash
   grep -oE '^\| *`(src|tests|scripts|docs)/[^`]*`' "$AUDIT" | sed -E 's/^\| *`//; s/`$//' > /tmp/rows
   sort /tmp/rows | uniq -d
   { find src/amoeba tests scripts -type f -not -path '*/__pycache__/*'; ls -dp docs/*; } |
   awk 'NR == FNR { rows[$0]; next }
        { for (r in rows) if (index($0, r) == 1) next; print "missing: " $0 }' /tmp/rows -
   ```

2. **Every verdict is valid.** Check the verdict column of each section 2 to 4 table for exactly `keep`, `rework`, `squadron` or `delete`. Search those rows for `keep`/`rework` paired with `none`. There should be no matches.

3. **The import coupling is reproducible.** Run the 5a scan from section 11. Its output should list the same import pairs as 5a, no more and no fewer. 5b is checked by reading. Confirm that nodes, journal entries, blocked states and the tick loop each appear in 5a or 5b.

4. **Slice 182 has a decision.** Run `git diff --stat main...182-slice.program-concept-as-a-source`. Every file listed should appear in section 6 under take, rewrite or drop.

5. **Squadron issues exist.** For each `squadron` row, run `gh issue view <n> -R ecorkran/squadron`. It should show an open issue that does not mention Amoeba.

6. **No code changed.** Run `git diff --stat main...220-slice.code-audit -- src tests scripts docs`. It should print nothing.

## Implementation Notes

### Development Approach

1. Create branch `220-slice.code-audit` from `main` and write the audit document's skeleton (frontmatter and the eleven section headings).
2. List every unit at D1 granularity.
3. Give verdicts to source units, the answering and store code first, because the rest of the tables depend on them.
4. Give verdicts to tests, scripts, docs and resources, following the source verdicts. A test of deleted code is deleted.
5. Run the 5a scan, and read for the 5b coupling. Write the scan command into section 11.
6. Sort the 182 diff (D5), and confirm the 180 pipeline (D7) and the live tests (D8).
7. File any Squadron issues (D6). Write the differences and the Summary.
8. Run the Verification Walkthrough. Add any note required in the 223 plan entry.

The slice follows the normal slice route: tasks, implementation on the branch, review, then merge in Phase 7. The only artifacts are the analysis document, any Squadron issues, and any one-line plan note.

### Special Considerations

- **Judge against the scenarios, not against what the code does well.** Well-tested code with no scenario gets `delete`. The architecture's goal of being small takes priority.
- **Tests of kept code may still be deleted.** Many tests of the answering code build nodes, journal entries or a tick. They are `rework` only if their claim still holds once those are gone. Otherwise they are `delete`, and 223 writes new ones.
