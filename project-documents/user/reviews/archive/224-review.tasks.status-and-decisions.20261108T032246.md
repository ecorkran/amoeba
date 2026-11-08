---
docType: review
layer: project
reviewType: tasks
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/224-tasks.status-and-decisions.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 5d26ec0deeef5b1af171dc20d6f65f902e88a88a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 112197
cachedTokens: 11198
cacheWriteTokens: 100995
completionTokens: 5410
durationSeconds: 44.1
costUsd: 0.46005
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "No store read supplies question rows for non-waiting runs, but `status_runs` assumes one exists"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:152-154"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Granularity: several small implementation and test pairs could merge"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:152-175"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "Task 4.3 adds a new contract document the design does not call for"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:213-216"
  - id: F004
    severity: note
    category: process
    summary: "Final commit message type does not match its content"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:243"
  - id: F005
    severity: note
    category: test-coverage
    summary: "`project_of` timeout is not explicitly tested"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:173-175"
  - id: F006
    severity: pass
    category: coverage
    summary: "Design coverage and sequencing"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md"
---

# Review: tasks — slice 224

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] No store read supplies question rows for non-waiting runs, but `status_runs` assumes one exists

- **Gap:** Task 3.10 (line 178) says to "read the question row and latest answer (already in the single store read)". The only store read tasks are 3.4 and the one under 3.12:
  - `open_questions` returns only `waiting_on_pm` rows.
  - The programs/members read returns no question rows at all.
- **What breaks:** `classify_pause` needs the row and latest answer outcome for the `claim_live`, `claim_stale`, `answered_unresumed`, `settled` and `waiting_on_pm` classes. Nothing provides those rows.
- **Ordering conflict:** Task 3.12 and the design both say the store is read before `sq runs list`, so run ids are not known at read time. The task must therefore either read all of the in-scope members' question rows plus latest answer outcomes up front, or add a second read after `list_runs`. The second option is fine because it is outside any subprocess call.
- **Fix:** Extend 3.4/3.5 to include this read, for example `questions_with_latest_answer(store, member_ids)`. Check 0.2's inventory for an existing 223 read that fits.

### [CONCERN] Granularity: several small implementation and test pairs could merge

- **Size:** There are about 40 subtasks for a slice rated 3/5 effort.
- **Candidates to merge:** 3.4/3.5 (open questions), 3.6/3.7 (scope) and 3.8/3.9 (placement) are each a few dozen lines of code. Each has its own implementation task and test task, with two success checks.
- **Suggested merges:**
  - Fold 3.4/3.5 into the store read that the previous finding requires.
  - Merge 3.6/3.7 into one "scope" task with its tests.
  - Keep 3.8/3.9 together as a single task, or leave them split and merge the others.
- **Why:** The test-with pattern is preserved either way, and the agent loses nothing in precision.
- **Also:** Task 1.4 (the `waiting_reason` pin) is justified by D5. It could sit inside 1.3's success criteria instead of being its own top-level task.

### [CONCERN] Task 4.3 adds a new contract document the design does not call for

- **Not in the design:** D8 and D9 require only the `docs/store-contract.md` update, which task 2.9 already covers. A new `docs/read-side-contract.md` with a "PauseClass table, `next` entries and exit codes" is not in the design's components or decisions.
- **Success criterion is vague:** "each operation, class, rejection code and exit code in the code appears in the doc" cannot be checked without a script.
- **Duplication:** This restates D3 and D8.
- **Options:** Cut 4.3 to a short pointer in `docs/store-contract.md`, or keep the document and add a mechanical check (for example, a test that every `PauseClass`/`RejectCode` value appears in the doc). Note that 4.3 also carries the conditional `squadron-hook.md` update.

### [NOTE] Final commit message type does not match its content

- **Mismatch:** The last marker is `test: record sq runs list fixtures and verify status and decisions`. It also covers 5.2, which changes `run_list.py` and deletes the proposed fixtures. Task 5.3 may add defect fixes as well.
- **Suggested change:** `feat:` or `fix:` fits better, or keep `test:` only if 5.2 stays fixtures-and-names only.
- **Related risk:** If 5.1 hits `BLOCKED: waiting on squadron#303`, the section 3 and 4 commits already exist and the slice is incomplete. The design acknowledges this, so nothing needs to change.

### [NOTE] `project_of` timeout is not explicitly tested

- **Gap:** D1 says a `project_of` timeout becomes a `lookup_failed` run. Task 3.9 tests `lookup_failed` for `CfCallFailed` but does not name the timeout case.
- **Fix:** Add "a timeout" to the `lookup_failed` case. This is a one-phrase addition.

### [PASS] Design coverage and sequencing

- **Decision coverage:**

  | Decision | Tasks |
  |---|---|
  | D1 | 3.1–3.3, 5.1–5.2 |
  | D2 | 3.6–3.7 |
  | D3 | 1.1–1.3, 3.10–3.11, the cross-check in 3.13 |
  | D4 | 3.8–3.12 |
  | D5 | 2.1–2.2, 2.5–2.6, 1.4 |
  | D6 | 2.3–2.4 |
  | D7 | 2.7–2.8 |
  | D8 | 4.1–4.2 |
  | D9 | 2.9 |
  | D10 | the fixture tasks |

- **Walkthrough:** Steps 1–7 are covered by 5.3.
- **Dependencies:** They run forward only, and the `classify_pause` extraction comes first with 223's tests unchanged as the gate. Work that does not need #303 (section 2) is separated from work that does (sections 3 and 5).
- **Commit markers:** They sit after the refactor, after the decisions/mark_read work, after `status`, after the CLI, and at the end, each at a green point.
- **Hand-written fixtures:** The design forbids hand-writing fixtures. The `runs_list_proposed` stand-ins are clearly labelled and replaced in 5.2, which is acceptable.
- **No load-test NFR:** The slice restates none, so none is required.

### Run Digest

- Response length: 5682 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 112197 / 11198 / 100995 / 5410 / not computed
- Duration: 44.1 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
