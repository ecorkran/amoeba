---
docType: review
layer: project
reviewType: tasks
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 43bc228b48f1f049e126d7936d3a492272bbe50f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 47.1
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 2.1 temporary cross-layer import risks a circular import"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:94"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Inconsistent granularity and commit handling for module moves"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:153-166, 226-246"
  - id: F003
    severity: concern
    category: completeness
    summary: "Status mapping for `ApiError` codes is not defined in the error-table task"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:359-364"
  - id: F004
    severity: concern
    category: task-scoping
    summary: "Task 3.5 bundles too much and has an ambiguous `NoAuth` placeholder"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:368-381"
  - id: F005
    severity: concern
    category: process-conformance
    summary: "Hallucination-trap examples in the gate task"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:46, 48"
  - id: F006
    severity: note
    category: coverage
    summary: "`read_listing()` and the snapshot helper are not assigned in this file"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:92"
  - id: F007
    severity: note
    category: nfr-coverage
    summary: "No load-test or CI-gating task"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:21"
  - id: F008
    severity: note
    category: sequencing
    summary: "Good traceability and checkpoint distribution in Group A"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:59-297"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success-criteria mapping for Group A and the Group B skeleton"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:81-415"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 2.1 temporary cross-layer import risks a circular import

Task 2.1 moves the registry types and `LISTINGS` into `amoeba.inspection`. It leaves entries for not-yet-moved listings importing row functions from `amoeba.cli` (`inspect_inbox`, `inspect_evidence`, and the 105–108 modules). Those `cli/inspect_*.py` modules import `Row`, `Listing`, and similar types from `cli/inspect.py`, which Task 2.1 repoints at `inspection.registry`. The result is a cycle: `inspection.registry` → `cli.inspect_*` → `inspection.registry`. The task calls this import "the only cross-layer import allowed" but gives no way to avoid the cycle. Either move all row modules unchanged first (relocation-only, still no signature change) and then do `registry.py`, or tell the implementer how the cycle is avoided. As written, a junior AI is likely to stall at Task 2.1.

### [CONCERN] Inconsistent granularity and commit handling for module moves

Task 2.5 moves three or more modules (105, 107 with calibration and checks, 108). Each is described as its own sub-step with the suite run after each, but the task produces one commit. Task 2.9 has the same structure (sub-steps 2.9a–f), yet it requires six commits. Task 2.9 also has effort 4 and covers six modules. Make the policy consistent: either split 2.5 and 2.9 into one task per module, or state that 2.5 is one commit and 2.9 is six. Splitting is better, because each 2.9 step needs its own byte-comparison gate and a failure should be isolated.

### [CONCERN] Status mapping for `ApiError` codes is not defined in the error-table task

Task 3.4 maps exception types to `(code, status)`, but `ApiError(code, message)` has no exception-type key. That is how the endpoint-raised codes would be raised: `request_too_large`, `request_timeout`, `listing_too_large`, `too_many_streams`, `unauthenticated`, `auth_unavailable`, `insufficient_scope`, `principal_mismatch`, `unknown_listing`, and `unknown_project`. The success criterion "Statuses are chosen only in this table" cannot hold unless the table also maps every `ApiErrorCode` to a status. Add a step that maps all `ApiErrorCode` members to statuses, and a test that every member has a status. Task 3.5's "every table entry" test then covers it.

### [CONCERN] Task 3.5 bundles too much and has an ambiguous `NoAuth` placeholder

Tasks 3.4 and 3.5 together deliver the error vocabulary, the error table, `query_from_params` (with its own tests), the app factory, a `NoAuth` stub, a layering AST test, and the error-table tests. `query_from_params` is an `inspection` concern that Task 2.6 already prepared for. It belongs next to the query tests, not in the serve error task. The `NoAuth` text ("placeholder … real in Task 6.3") is unclear. `NoAuth` is also the real `--auth none` implementation, so the task should say what is final and what changes later. Split out `query_from_params` with its tests into its own task. Clarify that `NoAuth` is final and that only `TokenAuth` arrives in Section 6.

### [CONCERN] Hallucination-trap examples in the gate task

Task 1.1 asks the implementer to retrieve names from the repo (listing modules, the location of the `Change` → JSON function). It places concrete example values right next to those instructions: "e.g. `calibration` and `cf-snapshots`", "expected `cli/feed.py`", and "expected `cli/inspect_feed.py`" in Task 2.4. The project CLAUDE.md names this pattern as a hallucination trap. If a lookup comes back empty, the model will reach for the nearby example. Rewrite these as "stop with an error if the listing or module is not found", and drop the example names.

### [NOTE] `read_listing()` and the snapshot helper are not assigned in this file

The LLD's `registry.py` lists `read_listing()` (the `read_transaction()` + `change_head` read) alongside `encode_rows()`. Task 2.10 adds only `encode_rows`, and neither Task 3.6 (supervisor listings) nor any other task in this file creates `read_listing`. I could not find the name in any of the three task files. Add it to the project-listings task (Tasks 3.8–3.10 in file 2), or to Section 2, so the snapshot-consistency criterion has an owner.

### [NOTE] No load-test or CI-gating task

The task file states there is no load or benchmark task, because the only latency bound is covered by a timing test (Task 5.7). That is reasonable, because the slice sets no throughput NFR. No task creates a `tests/load/` test or CI wiring, and a search of all three task files for CI or load references found none. The latency timing test and the stall and checkpoint tests should therefore be confirmed to run in the standard CI suite, or the PM should be told explicitly that none of them is gated separately.

### [NOTE] Good traceability and checkpoint distribution in Group A

Task 1.2 captures the byte-comparison baseline before any move. It iterates `LISTINGS`, so later listings are covered, and a missing baseline fails instead of skipping. Tasks 2.2 through 2.12 each gate on that comparison, commits are spread across the group, and Task 2.12 provides a reviewable checkpoint before any serve code. Tests follow implementation in 2.6/2.7 and 3.2/3.3, and the Task 3.4/3.5 pair also follows the pattern. Gate tasks (1.1) cover the 105–108 prerequisite and the PM-ratification dependencies (D2 before Group B, with the fallback noted).

### [PASS] Success-criteria mapping for Group A and the Group B skeleton

These LLD criteria and requirements trace to tasks in this file:
- **Registry move with no output change:** Tasks 1.2 and 2.1–2.5.
- **`ListingQuery` and the undeclared-option error:** Tasks 2.6–2.9.
- **No `argparse` and no re-export shims:** Tasks 2.9, 2.10, 2.12.
- **Layering and the writer guard:** Tasks 2.10 and 3.5.
- **`change_as_json` move:** Task 2.11.
- **`ServeSettings`, `is_loopback`, and the error vocabulary:** Tasks 3.2–3.5.
- **Listing discovery and supervisor listings:** Tasks 3.6–3.7.
- **Token-file-is-not-a-project:** the `serve` project-name half in Task 3.7.

I found no scope creep in this file. Every task traces to the LLD.

### Run Digest

- Response length: 7320 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 47.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
