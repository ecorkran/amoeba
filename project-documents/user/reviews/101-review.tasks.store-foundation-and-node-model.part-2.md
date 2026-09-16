---
docType: review
layer: project
reviewType: tasks
slice: store-foundation-and-node-model
project: amoeba
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 9fd07d4bbf3f0051aeef1b6a40c747134f26b14e
findings:
  - id: F001
    severity: concern
    category: gap
    summary: "Contract documentation task has no specified output location"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:126-146"
  - id: F002
    severity: concern
    category: gap
    summary: "Contract documentation task omits the CF/SQ reference fields, a named Included-scope item"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:132-138"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Public API surface (Task 5.1) has no automated regression test"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:108-124"
  - id: F004
    severity: concern
    category: clarity
    summary: "Failure-mode test task doesn't specify which test file receives the new tests"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:48-66"
  - id: F005
    severity: note
    category: test-coverage
    summary: "Permission-error test may be unreliable in root-run or containerized CI"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:56-57"
  - id: F006
    severity: pass
    category: correctness
    summary: "Disk-full failure mode is correctly excluded from the test task, matching the LLD precisely"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:34-37,55-58"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing in this file is sound and correctly chained to part 1"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:29"
  - id: F008
    severity: pass
    category: completeness
    summary: "Migration and walkthrough tasks mirror the LLD's own verification language almost verbatim"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:77-82,148-166"
---

# Review: tasks — slice 101

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Contract documentation task has no specified output location

Task 5.2 ("Write the contract documentation") lists six substantive documentation topics (API surface, vocabularies, writer model, failure modes, locality/migration, reversal trigger) but never states where this document lives. It has no `Files to Create` field — unlike every implementation and test task elsewhere in the breakdown (1.1, 1.4, 2.1, 2.3, 3.4, 3.7, 4.3 all specify concrete paths). The slice design's Component Structure (slice design lines 71-86) lists no docs file, README, or CONTRACT.md either — only `__init__.py`, the store modules, and test files. Task 5.1 already covers docstrings on exported callables, so 5.2 is clearly meant to produce something more (a standalone contract document, per the Integration Requirement that "a downstream author can design against it without reading the implementation" — slice design line 23/268), but a junior AI has nothing telling it whether to write a module-level docstring, a new `docs/contract.md`, or a package README. This is exactly the kind of deliverable ambiguity the task format elsewhere avoids by naming files explicitly.

### [CONCERN] Contract documentation task omits the CF/SQ reference fields, a named Included-scope item

The slice design lists "CF and SQ reference fields on nodes" as one of only seven bullet points under Technical Scope → Included (slice design line 35), and names slice 104 as a consumer of exactly these fields via the Integration Points section ("the reference fields its provenance correlates against," slice design line 236). Task 3.3 (file 1) implements updating these fields as opaque, unparsed values. Task 5.2's documentation steps enumerate "node writes" generically but never call out documenting the CF/SQ reference fields' opaque, non-parsed nature — a detail explicitly worth stating per the LLD ("Any parsing of CF or SQ output... the Runner parses them," Out of Scope line 203). A downstream author reading only the contract doc could reasonably not learn that these fields exist and must not be parsed, since no step requires writing that down.

### [CONCERN] Public API surface (Task 5.1) has no automated regression test

Every other implementation task in the two-file breakdown is followed by a dedicated test task or has test steps of its own (2.1→2.2, 2.3→2.4, 3.3→3.4, 3.5/3.6→3.7, 4.1→4.2). Task 5.1 (define exports in `__init__.py`) breaks that pattern: its only verification is Task 5.3's one-time manual REPL walkthrough ("Execute the REPL walkthrough from the LLD's step 3 against a temporary store," line 157). That walkthrough is not part of the `pytest` suite, so a later regression — a typo'd export name, a forgotten exception class, an accidentally-removed re-export — would not be caught by `uv run pytest`, only by someone manually re-running the walkthrough. Given this slice's stated purpose is a stable contract for initiatives 120/140/160, the import surface is exactly the kind of thing that should be pinned by an automated test (e.g., `from amoeba.store import Store, Node, NodeStatus, ... ` asserted in `tests/`), not left to manual verification alone.

### [CONCERN] Failure-mode test task doesn't specify which test file receives the new tests

Task 4.2 ("Test the failure modes") has no `Files to Create` field, unlike its sibling test tasks (2.2 → `tests/test_models.py`, 2.4 → `tests/test_migrations.py`, 3.4 → `tests/test_store.py`, 3.7 → `tests/test_queries.py`). The slice design's Component Structure (lines 80-85) enumerates exactly four test files, none named for failure modes. A junior AI has to guess whether these tests belong in `test_store.py` (since the failure modes live in `store.py`/`migrations.py`) or a new file — an ambiguity the rest of the breakdown deliberately avoids by naming files explicitly.

### [NOTE] Permission-error test may be unreliable in root-run or containerized CI

"Test opening a path the process cannot read or write raises at open" (Task 4.2) typically relies on `chmod`-based restriction, which is a no-op when the test process runs as root (common in Docker-based CI). The task doesn't flag this portability risk or suggest a fallback (e.g., skip-if-root, or restricting a parent directory instead of the file). Not blocking, but worth a note before this test is written so it doesn't silently pass-by-skip or fail in CI without diagnosis.

### [PASS] Disk-full failure mode is correctly excluded from the test task, matching the LLD precisely

The LLD's Functional Requirements explicitly list only three failure modes as requiring a test — "opening a corrupt database file, opening a path the process cannot read or write, and exhausting the busy timeout" (slice design lines 255) — deliberately omitting disk-full, which is implemented (Task 4.1, line 37) but correctly not required to be tested (Task 4.2 tests only three modes, lines 55-57). This is a subtle, easy-to-miss distinction that the task breakdown gets exactly right rather than either over- or under-testing.

### [PASS] Sequencing in this file is sound and correctly chained to part 1

Task 4.1's dependency on "Task 3.8" correctly anchors this file to the committed store API from part 1, and the remaining chain (4.1→4.2→4.3→4.4→5.1→5.2→5.3→5.4) is strictly linear with no circular references and no task assuming work from a later step.

### [PASS] Migration and walkthrough tasks mirror the LLD's own verification language almost verbatim

Task 4.3's success criteria ("the stamp advanced and pre-existing data survived") and Task 5.3's five verification steps track the slice design's Verification Walkthrough (slice design lines 271-326) closely enough that a reviewer can trace each step back to its source requirement without inference.
