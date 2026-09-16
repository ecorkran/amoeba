---
docType: review
layer: project
reviewType: tasks
slice: store-foundation-and-node-model
project: amoeba
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/101-tasks.store-foundation-and-node-model-1.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 9fd07d4bbf3f0051aeef1b6a40c747134f26b14e
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Task 3.2's row-mapping and context-manager guarantees have no owning test task"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-1.md:257-280"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Runnable/blocked queries aren't explicitly tested for cross-project isolation"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-1.md:348-388"
  - id: F003
    severity: concern
    category: gap
    summary: "Task 1.4's guard test references \"the central store path constant,\" which no task ever creates"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-1.md:90-112"
  - id: F004
    severity: pass
    category: test-coverage
    summary: "No load-test tier added, consistent with the LLD's explicit exclusion"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:180"
  - id: F005
    severity: pass
    category: sequencing
    summary: "Commit checkpoints are well distributed, not batched at the end"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-1.md:72-87"
  - id: F006
    severity: pass
    category: scope
    summary: "No scope creep; excluded items are enumerated and respected"
    location: "project-documents/user/tasks/101-tasks.store-foundation-and-node-model-2.md:192-205"
---

# Review: tasks — slice 101

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Task 3.2's row-mapping and context-manager guarantees have no owning test task

Task 3.2 (`store.py`: open/close/context-manager/row-mapping) lists success criteria including "a row with an out-of-vocabulary status raises" and "the context-manager form releases the connection on both normal and exception exit," directly echoing the LLD's Data Flow section ("An unmappable row raises; it never yields a partially-populated object," slice design lines 96-98). Every other implementation task in the breakdown is immediately followed by a dedicated test task (2.1→2.2, 2.3→2.4, 4.1→4.2), but 3.2 is followed by 3.3 (more implementation) and then 3.4, whose steps only cover CRUD round-trips and status-on-write validation — not a row physically containing an out-of-vocabulary status being read back, nor exception-exit behavior of the context manager. A junior AI following this breakdown literally has no task instructing it to write that test, so this specific "unknown is a value, not a default" guarantee at the storage boundary could ship unverified.

### [CONCERN] Runnable/blocked queries aren't explicitly tested for cross-project isolation

Functional Requirement 6 in the slice design states plainly: "queries for one project never return another project's nodes" (slice design line 254) — a blanket claim about all queries. Task 3.6's own success criteria assert "Both queries are project-scoped" (line 362), and Task 3.4 does cover cross-project isolation, but only for the basic CRUD/list-by-project/list-children paths (line 315: "Test project isolation: with two projects populated..."). Task 3.7, which tests `block()`/`resolve()` and the two Runner queries, has no step asserting that `runnable()`/`blocked()` scoped to project A never surface project B's nodes. This is the load-bearing pair of queries the Runner depends on, so the isolation guarantee deserves its own explicit assertion rather than inheriting untested confidence from the CRUD-level test.

### [CONCERN] Task 1.4's guard test references "the central store path constant," which no task ever creates

Task 1.4 requires "a test asserting no test module references the central store path constant" and a success criterion that this guard test "would fail if a test module reached for the central store path." This presupposes a named, centrally-defined default path (matching the LLD's "Store locality" decision — `~/.config/amoeba/`, XDG handling, environment override, slice design lines 126-134, which states "Exact path resolution... is settled during implementation," i.e., in scope for this slice). No task in either file assigns implementing that default-path resolution function/constant; Task 3.2's "resolve the store path" step (line 264) reads as accepting an already-supplied path, not computing the per-supervisor default. As written, either Task 1.4's guard test has nothing concrete to check against, or an implementer must invent the constant ad hoc without a task ever specifying its resolution rules (XDG override, `~/.config/amoeba/` convention). Recommend adding an explicit task for central-path resolution (or clarifying that this slice only accepts caller-supplied paths and defers default-path computation to slice 102, in which case Task 1.4's phrasing should be corrected).

### [PASS] No load-test tier added, consistent with the LLD's explicit exclusion

The slice design states this library sits on none of the simulation/network/concurrency/environment paths that require load tests (slice design lines 357-359). Task 5.4 explicitly confirms "no load-test tier was added" as a final-review step, so the review criterion about load-test/CI-gating tasks correctly doesn't apply here, and the breakdown makes that reasoning traceable rather than silently omitting it.

### [PASS] Commit checkpoints are well distributed, not batched at the end

Five commit checkpoints (Tasks 1.3, 2.5, 3.8, 4.4, 5.4) are spread evenly across both files, each gated on the full ruff/pyright/pytest verification trio passing first. No large batch of unverified work accumulates before a commit.

### [PASS] No scope creep; excluded items are enumerated and respected

The "Out of Scope" section explicitly lists every item the slice design excludes (resident process, command journal, inbox, findings/verdicts, change feed, pruning, CF/SQ parsing, per-project override), and no task in either file implements any of them. Every task traces to a concrete piece of the LLD's Technical Scope or Success Criteria.
