---
docType: review
layer: project
reviewType: tasks
slice: durable-inbox-and-message-queue
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-1.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: ea9e3e22620271d9a4887a68763abddd81cfcb05
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
findings:
  - id: F001
    severity: concern
    category: task-structure
    summary: "Three consecutive implementation tasks in Section 6 ship unverified behavior; test-with pattern broken"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:93-218"
    resolution: accepted
    resolvedBy: "task 6.8 gains explicit steps for the deferred 6.5/6.6 behavior"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "Crash-table row \"killed between store creation and the record commit\" has no covering task step"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:191-218"
    resolution: accepted
    resolvedBy: "task 6.8 gains the open_project-to-commit crash step"
  - id: F003
    severity: note
    category: accuracy
    summary: "Task 1.2 miscounts and misnames the writer-guard edit sites"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-1.md:56-82"
    resolution: accepted
    resolvedBy: "task 1.2 corrected to five sites; invented symbol removed"
  - id: F004
    severity: pass
    category: test-coverage
    summary: "Load-tier NFR is covered and CI gating is structural, not implicit"
    location: ".github/workflows/ci.yml:52-54"
  - id: F005
    severity: pass
    category: task-structure
    summary: "Sequencing, commit cadence, scope discipline, and factual premises all check out"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-1.md"
---

# Review: tasks — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Three consecutive implementation tasks in Section 6 ship unverified behavior; test-with pattern broken

Tasks 6.4 (apply loop), 6.5 (quarantine ladder), 6.6 (attempt counter and `failed/` park), and 6.7 (tenant registration) are implemented, committed, and built upon before any test task runs; the only coverage in between is Task 6.4's own smoke test, which covers batch size and `stop_requested` but none of the quarantine ladder or F001 behavior. The dedicated test task, 6.8, arrives three implementation tasks later (effort 9 cumulative). This violates the project guide's test-with rule ("tests gate forward progress ... before subsequent implementation tasks begin") — the same rule the breakdown itself follows diligently everywhere else (2.1→2.2, 2.3→2.4, 3.1→3.2, 3.3→3.4, 5.2→5.3). Task 6.5 and 6.6 are exactly the kind of behavior that needs immediate pinning: six distinct quarantine branches and a multi-start crash/park/requeue state machine whose success criteria ("the counter survives the crash that wrote it", "a requeued file resumes at its old count") cannot be verified inside those tasks at all. Task 6.8 also lists `tests/process/test_inbox_tenant.py` under "Files to Create" although Task 6.4 already creates it — a symptom of the deferred-testing split. Suggested fix: split 6.8, or add inline verification steps to 6.5 and 6.6 the way Task 3.5 does (implement-and-test in one task). Milder instances of the same pattern, not blocking: Section 4 (4.1→4.2→4.3) and Section 7 (7.1→7.2→7.3), and Task 5.1's envelope parse behavior (extra fields ignored, unknown version rejected) is not directly tested until 5.5.

### [CONCERN] Crash-table row "killed between store creation and the record commit" has no covering task step

The slice design's functional requirement — "a process killed between store creation and the record commit writes the record on restart" — is a distinct crash point (the LLD's crash table row: new empty store, file in `new/`, no record → store discovered at start, `open_project` finds it open, record written). Task 6.8's enumerated steps cover the other crash rows: "applied on start" for a pre-commit crash and "file restored to `new/` after apply" for the post-commit case, but the open_project/commit window is absent. Task 10.3's end-to-end `kill -9` also does not reach it — the walkthrough kills the process after the intent submission has already applied. Task 9.1's randomized kills only cover this window probabilistically, and a failure there would be hard to attribute. The success criterion "Every functional criterion in the LLD touching the tenant has a test here" in Task 6.8 presumably intends to catch this, but a junior AI executes the step list, not the inference. The scenario is concretely testable via `tests/host_harness.py` (create the store via `open_project`, close without applying, place the submission file in `new/`, restart, assert the record is written and applied once). Add an explicit step to Task 6.8.

### [NOTE] Task 1.2 miscounts and misnames the writer-guard edit sites

Task 1.2 says there are "the **four** other places" naming `process/host.py` literally and attributes the failure message to a helper named `_assert_no_read_write_open` — no such symbol exists in `tests/test_writer_guard.py`; the message lives in the parametrized `test_only_the_host_opens_a_store_read_write` (line 186). The actual literal occurrences beyond the constant at line 56 are five: the module docstring (line 5), the parametrized test's own docstring (line 177, not listed in the task), the failure message (line 186), the frozenset assertion (line 224), and the two test function names (lines 176, 223). The task's success criterion ("no `process/host.py` literal remains") is grep-verified and will catch everything regardless, so this wastes a little executor time rather than risking a wrong result — but the count and the symbol name should be corrected so the junior AI doesn't stop at four edits.

### [PASS] Load-tier NFR is covered and CI gating is structural, not implicit

The slice's Technical Requirement ("`tests/load/` gains a concurrent-submitter test with asserted exactly-once") is carried by Task 9.1 (`tests/load/test_inbox_concurrent.py`, explicitly placed in the existing tier) and Task 9.2 (measure-first drain bound, per the LLD's Implementation Notes). No new CI wiring task exists, and none is needed: the workflow created in slice 102 already runs `uv run pytest tests/load` as its own step that can fail the run independently, and the CI's default suite excludes the tier via `--ignore`, so the new test is gated the moment it lands in `tests/load/`. The gating is mechanical, not implicit. Task 10.4's final gate re-runs both tiers.

### [PASS] Sequencing, commit cadence, scope discipline, and factual premises all check out

Verified against the slice design and the codebase: the dependency chain 1.1→1.2→…→10.4 is acyclic and matches the LLD's Development Approach order (extraction first as a pure refactor with the writer-guard move before `open_project`; consolidation before D3 behavior; models before migration; `apply_submission` before the package); every one of the 33 tasks has a commit checkpoint distributed throughout rather than batched; every task traces to a slice-design requirement (the `ProjectStores` extraction, migration 004 with backfill, D3 and both recovery consequences, D4 ordering, all three kinds and their rejection branches, the quarantine ladder, F001's bounded attempts, the CLI, the guard/public-API tests, the demo script from the walkthrough, the load tier, and all three documentation targets), with no scope creep found — Task 5.1's `validate_project_id` extraction and Task 9.2's measurement step are both explicitly grounded in the LLD's "Project ids become filenames" and "measure first" rules, and I confirmed their premises in `src/amoeba/store/paths.py` and slice 102's load-tier precedent. Task sizing is appropriate (effort 1–3, no task needs splitting; the effort-1 tasks are coherent units, not fragments).

## Response

All three findings accepted and resolved on 20260922. Each code-level claim was verified against source first; all held.

**F001 — accepted.** Correct that Tasks 6.5 and 6.6 stated success criteria no one could check inside those tasks — "the counter survives the crash that wrote it", "a requeued file resumes at its old count" are runtime behavioral claims, and the junior would have been ticking boxes it had no way to verify. Rather than splitting 6.8, its step list now carries explicit assertions for each deferred behavior, including the park transition and the `StoreError` boundary (see the part-2 review's F001 and F003, which found the same stretch from the other side). The duplicate `tests/process/test_inbox_tenant.py` under Files to Create is also fixed.

**F002 — accepted, and the best finding across both reviews.** The LLD's crash table has a distinct row — killed between store creation and the record commit — that is also a functional success criterion, and none of Task 6.8's eight steps reached it. The reasoning for why the catch-all criterion did not save it is exactly right: a junior AI executes the step list, not the inference. Task 6.8 gains a concrete step using the harness — create via `open_project`, close without applying, leave the file in `new/`, restart, assert the record is written and the effect happens once — with a note that Task 9.1's randomized kills hit this window only by chance and Task 10.3's `kill -9` lands after the submission has already applied.

**F003 — accepted, and it caught a defect introduced while fixing the previous review.** Confirmed: `_assert_no_read_write_open` does not exist in `tests/test_writer_guard.py`; the failure message lives in the parametrized `test_only_the_host_opens_a_store_read_write`. That symbol name was invented rather than checked. The literal occurrences beyond the constant are five, not four — the docstring at line 177 was missed — plus both test function names. Task 1.2 now lists all five, says to rename both tests, and ends with a grep so the count is a guide rather than the check.

### Run Digest

- Response length: 7385 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 75228
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
