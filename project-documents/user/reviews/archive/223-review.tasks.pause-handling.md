---
docType: review
layer: project
reviewType: tasks
slice: pause-handling
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/223-tasks.pause-handling.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: d2e6c886a4c65d53822d8f4ebfebf2b9452f1f05
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 119401
cachedTokens: 11198
cacheWriteTokens: 108199
completionTokens: 6948
durationSeconds: 57.6
costUsd: 0.504247
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Result types are used before they are defined, and `ResumeResult` is never defined"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:229"
  - id: F003
    severity: concern
    category: clarity
    summary: "Answer-limit check across tasks 1.6 and 5.7 is ambiguous"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:86"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Tasks 7.4 and 7.6 are oversized"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:277"
  - id: F005
    severity: note
    category: proportionality
    summary: "Small items that can be trimmed"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:242"
  - id: F006
    severity: note
    category: scope
    summary: "`handle_pause` split into three modules departs from the design"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:37"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit markers"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:105"
---

# Review: tasks — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are fully covered

Each criterion in the slice design maps to tasks:
- **Answered and resumed on a real run:** 9.2 (live) and 10.2 (walkthrough).
- **Barred, then allowed after `set_up`:** 5.8 (unit) and 10.2.
- **`answer` records, resumes, and becomes precedent:** 1.8, 4.7, 7.8, 7.9.
- **The four checks pass:** 10.1.
- **`answering.yaml` has no hard-coded authorize list:** 3.2 and 10.1.
- **The three contract and hook docs:** 5.3, 8.3, 9.1.
- **Live tier and restored tests:** 9.2 and 9.3.
- **The #303 comment:** 9.4.

D15's unit coverage is also present: each `SkipReason` (7.3, 7.5, 7.7), the D7 rows (7.7), the D8 branches (6.2), no open transaction during a subprocess (5.6, 6.2), the compare-and-set guards (1.7), and migration 002 on a version-1 store (1.2).

Nothing is scope creep. The extra modules (`deps.py`, `pause_models.py`, `pause_eligibility.py`, `pause_existing.py`) are justified in the Context Summary by the ~300-line guideline.

### [CONCERN] Result types are used before they are defined, and `ResumeResult` is never defined

- **Task 5.7:** returns a `superseded` result, but the result models are only defined in 7.1.
- **Task 6.1:** returns `ResumeResult`, and no task says where it lives or what fields it has. Task 7.8's `AnswerResult` and 7.4's `HandlePauseResult` both embed it, along with `refused` and `not_delivered`. A junior implementing 5.7 and 6.1 must guess.
- **Fix:** move 7.1 ahead of 5.7, or into section 5. Add `ResumeResult` to it (outcome, detail, log path), and name the type that 5.7's `settle` returns.

### [CONCERN] Answer-limit check across tasks 1.6 and 5.7 is ambiguous

Task 1.6 says `settle_answered` "re-count[s] `prior` inside" the transaction. Task 5.7 runs `evaluate_gate` in the answering library, which does not import `store`, using a `prior` counted "inside the settle transaction". The tasks never say what the in-transaction re-count does:
- It could fail the settle when the count has reached the limit.
- It could re-run the gate.
- It could just refresh the number passed in.

The `settle_answered` return contract (true or false) is also unclear for this case. Task 5.8 tests only the gate at the limit, so the concurrent case (two answers racing past the limit) is untested. Pin down the intended behavior in 1.6 and 5.7, or drop the in-transaction re-count if the gate is the final word.

### [CONCERN] Tasks 7.4 and 7.6 are oversized

- **Task 7.4** bundles seven steps: resolve member, limit pre-check, gather, scratch, insert-or-lose race, start/wait/settle, and resume-only-if-answered. It has one success line.
- **Task 7.6** bundles three unrelated families: the answered-resume path, the waiting/settled skips, and the D7 claim table. The D7 table is about nine branches, including `replace_claim` with a second `gather` and a new scratch.
- **Fix:** split 7.6 into "answered/waiting existing rows" and "claimed row (D7)", each with its own test task. Consider moving 7.4's limit pre-check and failure-to-`waiting_on_pm` inserts into a helper task. This keeps each task completable by a junior in one pass and keeps functions near the 50-line guideline.

### [NOTE] Small items that can be trimmed

- **6.0:** "a test builds a `Deps` from fakes and shows it is immutable" tests a frozen-dataclass attribute no criterion needs. Drop it, since 6.2 and 7.x exercise `Deps`.
- **3.6:** the "add a forbidden import, verify once, then revert" step dictates process the criteria don't require. A passing boundary test is enough.
- **8.3:** "check `config-contract.md` against the code" duplicates 5.3, which already updated the doc.

### [NOTE] `handle_pause` split into three modules departs from the design

The design lists a single `handle_pause.py`. The tasks split it into `pause_models`, `pause_eligibility`, `pause_existing` and `handle_pause`, with re-exports preserving the design's import path. This is explained in the Context Summary and 7.1 and is acceptable. Tasks 7.2, 7.4 and 7.6 should state which module owns each function so the import direction (`handle_pause` → `pause_eligibility`/`pause_existing`, with `pause_existing` using `Deps`) stays acyclic.

### [PASS] Sequencing, test-with pattern and commit markers

The order is store, run file and fixtures, library, context, answering run, resume, operations, CLI, then live tier and docs. Dependencies are respected, apart from the result-type issue above. Every implementation task is followed by its test task. There are eight `**Commit**:` markers, each at a tested point, and a final marker after validation. They are plain lines, not checkboxes. Recording real `sq` and `cf` fixtures before the code that consumes them follows the parser-fixture rule.

No NFR is restated in the slice, so no load test or CI-gate task is required.

### Run Digest

- Response length: 5719 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 119401 / 11198 / 108199 / 6948 / not computed
- Duration: 57.6 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
