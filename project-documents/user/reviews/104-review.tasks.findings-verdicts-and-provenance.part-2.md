---
docType: review
layer: project
reviewType: tasks
slice: findings-verdicts-and-provenance
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: e55015bfc81092cb5a22a53333655a5f87e3036d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every Section 6–8 success criterion traces to a task"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing is a clean, acyclic chain with correct cross-file linkage"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md:27"
  - id: F003
    severity: pass
    category: process
    summary: "Commit checkpoints are per-task, not batched at the end"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "No explicit test for rejecting a verdict submission with a missing/empty `upstream_version`"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md:105"
  - id: F005
    severity: note
    category: sequencing
    summary: "Task 7.1 has no dedicated test task immediately after it"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md:120-137"
  - id: F006
    severity: note
    category: nfr
    summary: "No new load-test/CI-gating task, correctly so"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md:258"
---

# Review: tasks — slice 104

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Every Section 6–8 success criterion traces to a task

The slice's Development Approach steps 5–7 map 1:1 onto Sections 6, 7, and 8. The `verdict` inbox kind, the new `amoeba submit` flag rule, `value_options`, the two listings, the demo script, the end-to-end CLI test, and the doc updates (`evidence-contract.md`, `store-contract.md`, `inbox-contract.md`, `CHANGELOG.md`) each have a dedicated task, and each task's steps quote the LLD's exact language (e.g. Task 6.3's payload-flattening rule matches "The inbox `verdict` type" in the slice design almost verbatim). No task in this file is untraceable to a line item in the slice's Included scope or Success Criteria.

### [PASS] Sequencing is a clean, acyclic chain with correct cross-file linkage

Task 6.1 depends on Task 5.2 from part 1 (correctly referenced across files), and every subsequent task depends only on its immediate predecessor (6.1→6.2→6.3→6.4→7.1→7.2→7.3→8.1→8.2→8.3→8.4). No forward references, no cycles. Task 6.3's reuse of "Task 4.1's check helper" and "Task 4.1's insert helper" is consistent with part 1's Task 4.1, which explicitly split those helpers out for this purpose (104-tasks...-1.md:229-230).

### [PASS] Commit checkpoints are per-task, not batched at the end

Every one of the 11 tasks (6.1 through 8.4) ends with an explicit commit step and example message. Task 8.4 is the only end-of-slice task, and it's legitimately terminal (final validation + walkthrough write-up), not a dumping ground for deferred commits.

### [CONCERN] No explicit test for rejecting a verdict submission with a missing/empty `upstream_version`

The slice's functional requirement "A verdict without `upstream_version` cannot be recorded" is tested for the direct-call path in part 1 (Task 4.2: "empty `upstream_version`" is one of the failing-check tests). Task 6.4's rejected-path bullet only lists "a provider failure with findings, and one with a non-`UNKNOWN` verdict... an unknown node" — it never calls out an empty/missing `upstream_version` case through the inbox. The effect is built by reusing Task 4.1's check helper (per Task 6.3), so this will very likely pass once implemented, but the task list doesn't require a test asserting it, so a regression here (e.g. if the reused-helper wiring is done incorrectly) wouldn't be caught by any task in this breakdown. Add one bullet to Task 6.4 covering this case explicitly.

### [NOTE] Task 7.1 has no dedicated test task immediately after it

Unlike the 6.1→6.2 and 6.3→6.4 pairs, Task 7.1 (add `value_options` to the registry) is followed by more implementation (Task 7.2) before any test task (7.3) verifies it. This is defensible — `value_options` has no observable behavior until a listing consumes it — but it's a deviation from the test-immediately-follows-implementation pattern used elsewhere in this file, worth noting rather than blocking.

### [NOTE] No new load-test/CI-gating task, correctly so

The slice design has no NFR or performance section, and `tests/load/` already exists from prior slices (101–103). Task 8.4's `uv run pytest tests/load` is a regression check, not a new load test for this slice's functionality, so the "load test → CI wiring" requirement doesn't apply here. No gap.

## Response

- **F004 (CONCERN, accepted):** Task 6.4's rejected-path bullet didn't cover empty/missing `upstream_version`, even though the check is proven at the direct-call layer (part 1, Task 4.2). Added "An empty `upstream_version` is `rejected` with a reason" to Task 6.4's steps.
- F001, F002, F003 (PASS): no action needed.
- F005, F006 (NOTE): no action needed, reasoning in the finding stands.

### Run Digest

- Response length: 4188 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
