---
docType: review
layer: project
reviewType: tasks
slice: request-runs
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/184-tasks.request-runs.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 23d8b24b5ae5d83bd07bfba87aeae27ef96a3221
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
effort: xhigh
turns: 30
promptTokens: 1394378
cachedTokens: 1196572
cacheWriteTokens: 197786
completionTokens: 81734
durationSeconds: 487.0
costUsd: 0.450247
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "A `replied` request that is superseded has no test"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:206"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`ProgramView.readiness` has no defined value between Tasks 3.3 and 6.9"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:137"
  - id: F003
    severity: concern
    category: format
    summary: "Nested items under 0.1 have no checkboxes"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:64"
  - id: F004
    severity: note
    category: verification
    summary: "Task 0.1 does not record that `resolve_checkout` moves"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:189"
  - id: F005
    severity: note
    category: scope
    summary: "Task 8.3 adds checks beyond the design's criteria"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:256"
  - id: F006
    severity: note
    category: metadata
    summary: "Frontmatter dependencies omit 120, which the body relies on"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:6"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria and decisions map to tasks"
    location: "project-documents/user/slices/184-slice.request-runs.md:482-514"
  - id: F008
    severity: pass
    category: verification
    summary: "The load case is already gated in CI"
    location: ".github/workflows/ci.yml:54"
  - id: F009
    severity: pass
    category: verification
    summary: "The no-migration claim for `request` nodes and `sq_request` holds"
    location: "src/amoeba/store/schema/003_command_journal.sql:17"
  - id: F010
    severity: pass
    category: sequencing
    summary: "Sequencing, commit markers and the merge rule follow the conventions"
    location: "project-documents/user/tasks/184-tasks.request-runs.md"
---

# Review: tasks — slice 184

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] A `replied` request that is superseded has no test

D10 says supersession moves a `replied` request to `withdrawn`. Task 6.8, step 2, describes withdrawing it when its edge closed, but the test list (line 206) only covers a superseded `pending` request. Task 7.2 (line 234) covers pre-launch and `running` supersession, not `replied`. A regression in that branch would pass the suite. Add one case to 6.8: supersede the edge while the request is `replied`, then assert `withdrawn` and no binding.

### [CONCERN] `ProgramView.readiness` has no defined value between Tasks 3.3 and 6.9

Task 3.3 adds a required `readiness` field to `ProgramView` but defers filling it to 6.9, and says "until then `tick.py` passes `ProgramReadiness(...)`". Per 183's design (slice line 186), the program stage's result becomes `ProgramView`, not `tick.py`. So the field needs a value in the stage from 3.3 to 6.9. The options are a placeholder such as `EMPTY` (a silent fallback the rules forbid) or an unset required field (a strict pyright failure). Add the field in 6.9, where the stage fills it, and keep 3.3 to the three readiness-taking functions and `tick.py`'s construction of the value.

Related: 3.3 already edits `tick.py`, but 6.9 says "First, before adding anything" for the `_launch_context` extraction. Either move that extraction ahead of 3.3 or drop the phrase.

### [CONCERN] Nested items under 0.1 have no checkboxes

Lines 64–68 are the five name and test-file items under 0.1. They are plain bullets without `[ ]`, but the project's checklist rule requires a checkbox on each item and subitem. Task-checker cannot tick them, so the gate's evidence list is not tracked. Add `[ ]` to each.

### [NOTE] Task 0.1 does not record that `resolve_checkout` moves

Task 6.4 calls `resolve_checkout` with no module. It is currently defined in `src/amoeba/runner/dispatch/checkout.py:47`. 181's design (`project-documents/user/slices/181-slice.program-record.md`, around line 199) moves it, along with `Checkout` and `CheckoutUnresolved`, to `amoeba.upstream.context_forge`. The name list in 0.1 (lines 64–68) does not record the move, so the import path would have to be guessed after 181 merges. Add it to the list.

### [NOTE] Task 8.3 adds checks beyond the design's criteria

The design requires that the locality proof cover `requests` (slice line 503). Task 8.3 also adds a check that `request` nodes and `sq_request` entries live only in project stores. That is not in the design's criteria, though D3 gives its rationale, so either cite D3 or drop it. The negative test that an unknown program-store table still fails (line 257) tests existing oracle behaviour and can go.

### [NOTE] Frontmatter dependencies omit 120, which the body relies on

The Context Summary (line 44) names 120's `checkout_holders`, `PlanStage`, `SortKey` and related code as dependencies. The frontmatter list (lines 6–14) does not include 120. The slice design's frontmatter has the same omission, so correct both or record the gap.

### [PASS] Success criteria and decisions map to tasks

I checked 14 functional, 7 technical and 2 integration criteria. Each maps to a task with a test. Examples: one-tick ordering (3.5, 6.9), no-overlap and checkout waits (6.4, 6.8), binding after a fresh read (5.1, 6.2, 6.8), the two crash windows (6.10), `member_referenced` (1.6), the no-program regression (0.2, 6.9), the call-count criteria (6.4, 6.7) and the walkthrough (8.1, 8.2, 9.2). The gap is the `replied` row above. Apart from the 8.3 check, nothing is outside the design's scope.

### [PASS] The load case is already gated in CI

Task 8.4 adds a case to `tests/load/test_program_load.py`. CI already runs `uv run pytest tests/load` as its own step, so the new case is gated without a new CI task.

### [PASS] The no-migration claim for `request` nodes and `sq_request` holds

`command_journal.kind` is `TEXT NOT NULL` with no `CHECK`, and `nodes.kind` is the same (`001_initial.sql:16`). Task 2.1's "add no migration" is correct.

### [PASS] Sequencing, commit markers and the merge rule follow the conventions

Every dependency points to an earlier task, with no cycles. No task merges or pushes; the merge stays in Phase 7. Implementation tasks carry their tests, or the tests come in the next task (1.1 → 1.2). The 15 `**Commit**:` markers are plain lines at the ends of groups, and each sits at a tested point.

### Run Digest

- Response length: 8144 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 30
- Tokens — prompt / cached / cache write / completion / reasoning: 1394378 / 1196572 / 197786 / 81734 / not computed
- Duration: 487.0 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Resolution

- **F001 [concern] `replied` supersession untested:** fixed. Task 6.8's tests now also withdraw a `replied` request with no binding when its edge is superseded.
- **F002 [concern] `ProgramView.readiness` undefined between 3.3 and 6.9:** fixed. Task 3.3 no longer touches `ProgramView`; `tick.py` builds `ProgramReadiness` from `ProgramView.waiting` and `.providing` until Task 6.9, which adds the `readiness` field to `ProgramView`, fills it in the stage and replaces that construction. The "First, before adding anything" phrase in 6.9 became "Extract before wiring the stage".
- **F003 [concern] 0.1 sub-items lack checkboxes:** fixed. All five name and test-file items now have `[ ]`.
- **F004 [note] `resolve_checkout` moves:** fixed. The 181 item in Task 0.1 records that `resolve_checkout`, `Checkout` and `CheckoutUnresolved` move to `amoeba.upstream.context_forge`, and that Task 6.4 imports from there.
- **F005 [note] Task 8.3 beyond criteria:** fixed. The `request`-node and `sq_request` locality check now cites D3 and the LLD's locality rule; the unknown-table negative test (existing oracle behavior) was removed.
- **F006 [note] Frontmatter omits 120:** fixed in the task file (`120` added to `dependencies`). The slice design's frontmatter has the same omission and was left unchanged; recorded here as a known gap.
- **F007–F010 [pass]:** no change needed.
