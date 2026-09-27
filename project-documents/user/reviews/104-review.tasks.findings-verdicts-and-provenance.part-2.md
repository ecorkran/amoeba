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
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: e406ad9cc0489c1e3177ba9353eec79894a6dac1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Complete coverage of the slice design's Sections 6–8 success criteria"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies, and test-with pattern verified against the real code"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Adding VERDICT breaks two pinned submit tests that no task is scheduled to fix until 6.4 — and 6.4 claims they pass unchanged"
    location: "tests/cli/test_submit.py:76-91"
  - id: F004
    severity: concern
    category: process
    summary: "Tasks 6.1, 6.3, and 7.1 have no commit checkpoint"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-2.md"
  - id: F005
    severity: note
    category: nfr
    summary: "No new load test, and none is required — CI gating already exists"
    location: ".github/workflows/ci.yml:54"
  - id: F006
    severity: note
    category: environment
    summary: "The captured review files named in the slice design are not present in this checkout"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md"
  - id: F007
    severity: note
    category: docs
    summary: "LLD-internal tension: \"the writer guard is unchanged\" vs. the walkthrough's deliberate widening"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md"
---

# Review: tasks — slice 104

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Complete coverage of the slice design's Sections 6–8 success criteria

Every requirement in scope for this file maps to a task: inbox rejection of a provider failure with findings or a non-`UNKNOWN` verdict (Task 6.2, complementing Task 4.2's direct-call coverage in part 1); submission-id record id, replay no-op, and `INVALID_PAYLOAD` quarantine (Task 6.2); the one-rule submit flag builder (6.3/6.4); `value_options` and both listings with running/stopped behavior (7.1–7.3); the demo script with real fixture text and writer-guard widening (8.1); the end-to-end CLI requirement (8.2, modeled on the existing `tests/cli/test_inbox_end_to_end.py`); the contract docs and `CHANGELOG` (8.3); and all four tooling checks plus the walkthrough fill-in (8.4). Nothing in the slice's Included scope is missing, and no task lacks a traceable LLD anchor — the FindingPayload model Task 6.1 creates is the LLD's own component for typing the nested findings list, not scope creep. Task sizing (effort 1–3) is appropriate; no task needs splitting or merging.

### [PASS] Sequencing, dependencies, and test-with pattern verified against the real code

Dependencies form a clean linear chain (6.1 → 6.2 → 6.3 → 6.4 → 7.1 → 7.2 → 7.3 → 8.1 → 8.2 → 8.3 → 8.4) with no cycles, and the cross-file dependency on part-1's Task 5.2 is declared. Test tasks immediately follow their implementations. All anchors the tasks plan to replace or extend exist exactly as described: `test_slice_104_listings_are_not_registered_here` (`tests/test_cli_inspect.py:380`), the unregistered-findings test (`tests/test_cli_inspect.py:373`), the completeness tests (`tests/inbox/test_envelope.py:55`, `tests/store/test_inbox_apply.py:69`), the `demo_inbox.py` precedent (`scripts/demo_inbox.py`, `PERMITTED_SCRIPTS` at `tests/test_writer_guard.py:63`), and the registry append point (`src/amoeba/cli/inspect.py:149`; `cli/main.py` already iterates `LISTINGS` at `src/amoeba/cli/main.py:161`, so Task 7.2's "no more than the registry append and imports" claim is accurate).

### [CONCERN] Adding VERDICT breaks two pinned submit tests that no task is scheduled to fix until 6.4 — and 6.4 claims they pass unchanged

Task 6.1 adds `VERDICT` to `SubmissionKind`. That immediately falsifies two tests the task plan never touches: `test_every_kind_has_a_subcommand` asserts `set(KIND_FLAGS) == set(SubmissionKind)` (`tests/cli/test_submit.py:84`), and the parametrized write test at `tests/cli/test_submit.py:87-91` will invoke `submit verdict` with the (empty) `KIND_FLAGS` entry and fail payload validation. Task 6.2's success criterion "`uv run pytest` passes" is therefore unachievable as written — its Files-to-Modify list covers only the envelope and apply completeness tests, not `tests/cli/test_submit.py`. Task 6.4 does modify that file but only replaces `_takes_object` tests; its step "103's existing submit CLI tests pass unchanged apart from the replaced helper tests" is contradicted by the `KIND_FLAGS` completeness pin, which requires a new `VERDICT` entry with a full valid flag set (derivation, fallback-used, findings-parsed, provider-failure, findings, and provenance are all required by Task 6.1's payload). Either Task 6.2 or Task 6.4 should explicitly add the `KIND_FLAGS` entry and drop the "pass unchanged" wording; otherwise a junior following the checklist hits a red suite with no instruction on the fix.

### [CONCERN] Tasks 6.1, 6.3, and 7.1 have no commit checkpoint

Project rules require "Git add and commit from project root at least once per task." Commits appear only in the paired test tasks (6.2, 6.4, 7.3) — their messages are feature messages (`feat(inbox): add verdict submission kind`), showing the intended convention is commit-per-implementation+test-pair — but Tasks 6.1, 6.3, and 7.1 list no commit in their success criteria. A junior executing these checklists literally will leave completed implementation work uncommitted across a task boundary; a session interruption loses it. Add a commit checkpoint to each, or state the pair-commit convention explicitly in the Context Summary so the omission is clearly deliberate.

### [NOTE] No new load test, and none is required — CI gating already exists

The slice design restates no load/performance NFR; the new verdict effect runs inside 103's existing single-transaction `apply_submission` drain, which the existing tier (`tests/load/test_inbox_concurrent.py`, `test_crash_loop.py`) already exercises generically. CI already gates `uv run pytest tests/load` (`.github/workflows/ci.yml:54`), and Task 8.4 runs the tier clean. The tier-requirement rule is satisfied without a new load test; no action needed.

### [NOTE] The captured review files named in the slice design are not present in this checkout

The Technical Requirements table lists the four captured 102 task-review files under `project-documents/user/reviews/` (including `archive/`), and states they are "all tracked in git" — but that directory does not exist in this working tree (`project-documents/user/` contains only architecture, notes, project-guides, slices, and tasks), and `tests/fixtures/sq_reviews/` currently holds only the two JSON captures. Both part-1 Task 1.1 (which guards with "stop and ask the PM") and part-2 Task 8.1 (whose payload text must trace to fixture files Task 1.1 creates) have correct stop-guards for this, so the breakdown handles the situation — but the PM should confirm the files' location or commit them before Section 1 is scheduled, since Task 8.1's chain depends on them.

### [NOTE] LLD-internal tension: "the writer guard is unchanged" vs. the walkthrough's deliberate widening

The Technical Requirements say "The writer guard is unchanged," while the Verification Walkthrough and Task 8.1 add `demo_evidence.py` to `PERMITTED_SCRIPTS` (as 103 did for `demo_inbox.py`, `tests/test_writer_guard.py:63`). Task 8.1 resolves this precisely — widen by exactly one script, update the pinned-set assertion at `tests/test_writer_guard.py:288` and its comment — so no task change is needed, but the LLD's requirement bullet should be read as "no weakening," which the doc could state to avoid a reviewer flagging the widening as a violation.

### Run Digest

- Response length: 7956 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 2
- Stop reason: stop
- Reasoning characters: 43510
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response

Resolved 20260926 against `e406ad9`.

- **F003 (concern): accepted, and worse than stated.** Registering `VerdictPayload` makes `amoeba submit` build a `verdict` subcommand, and today's `_takes_object` raises `TypeError` at parser build on its bool and list fields. Every CLI test, not just the two `KIND_FLAGS` pins, would fail from the old 6.1 until the old 6.3. Section 6 is reordered: 6.1/6.2 replace and test the flag rule first (using a test-local pydantic model), then 6.3/6.4 add and test the verdict kind. Task 6.4 now adds the `VERDICT` entry to `KIND_FLAGS` with a full valid flag set, and the "pass unchanged" wording was removed from the task that changes that file.
- **F004 (concern): accepted, more widely.** Tasks 7.1 and 7.2 lacked a commit step, and so did seven implementation tasks in part 1 (1.2, 2.1, 3.1, 3.2, 4.1, 4.3, 5.1). Every task in both files now ends with a commit, per the project rule of at least one commit per task.
- **F006 (note): premise wrong, no change.** The four captured files are tracked in git under `project-documents/user/reviews/archive/`. See part 1's F001 response: the reviewer's tools cannot see `project-documents/user/reviews/`.
- **F007 (note): accepted.** The slice design's Technical Requirements bullet now reads "the writer guard is not weakened", naming the one permitted-script addition.
- **F005 (note):** no action.
