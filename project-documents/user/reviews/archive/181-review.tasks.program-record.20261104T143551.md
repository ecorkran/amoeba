---
docType: review
layer: project
reviewType: tasks
slice: program-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/181-tasks.program-record.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: d75e25d3b38bd39210bd4664887086ad59451cfe
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 529006
cachedTokens: 367161
cacheWriteTokens: 161835
completionTokens: 71061
durationSeconds: 370.4
costUsd: 0.217543
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion has a task, and no task is outside the design"
    location: "project-documents/user/tasks/181-tasks.program-record.md"
  - id: F002
    severity: pass
    category: traceability
    summary: "Parent architecture carries the D4 amendment"
    location: "project-documents/user/architecture/180-slices.program-coordination.md:152"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Refactor commits contradict the \"commit on their own\" rule"
    location: "project-documents/user/tasks/181-tasks.program-record.md:68"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 9.1's exception list omits the planned edits to existing tests"
    location: "project-documents/user/tasks/181-tasks.program-record.md:268"
  - id: F005
    severity: concern
    category: process
    summary: "The walkthrough notes and check-offs may never be committed"
    location: "project-documents/user/tasks/181-tasks.program-record.md:275"
  - id: F006
    severity: concern
    category: clarity
    summary: "`updated_at` behaviour on re-submission is not specified"
    location: "project-documents/user/tasks/181-tasks.program-record.md:122"
  - id: F007
    severity: concern
    category: clarity
    summary: "Detail text is undefined for two of the five unreadable reasons"
    location: "project-documents/user/tasks/181-tasks.program-record.md:180"
  - id: F008
    severity: concern
    category: coverage
    summary: "The quarantine test does not check that `invalid_payload` names the field"
    location: "project-documents/user/tasks/181-tasks.program-record.md:168"
  - id: F009
    severity: note
    category: traceability
    summary: "The dependency on 140 appears in one place and is missing from two"
    location: "project-documents/user/tasks/181-tasks.program-record.md:43"
  - id: F010
    severity: note
    category: granularity
    summary: "Task 2.6 is the largest store task"
    location: "project-documents/user/tasks/181-tasks.program-record.md:116"
  - id: F011
    severity: note
    category: granularity
    summary: "Two small tasks could fold into neighbours"
    location: "project-documents/user/tasks/181-tasks.program-record.md:93"
  - id: F012
    severity: note
    category: process
    summary: "Task 9.2 stops on a missing `sq` without attempting setup"
    location: "project-documents/user/tasks/181-tasks.program-record.md:270"
  - id: F013
    severity: note
    category: coverage
    summary: "\"Nothing raises for a member\" is not guaranteed once the store has opened"
    location: "project-documents/user/tasks/181-tasks.program-record.md:223"
---

# Review: tasks — slice 181

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion has a task, and no task is outside the design

Functional criteria map to 2.4–2.9 (rejections, replace and upsert, reused ids), 3.1–3.5 and 4.1–4.4 (submission, inbox, store creation), 5.1–5.2 and 7.3 (unreadable reasons on `program-blocked`), and 6.1–6.2 (stage placement, no-program regression, store-failure exit). Technical criteria map to 1.1–1.3, 5.3, 8.1–8.2 and 9.1. Docs map to 8.3–8.6, and the walkthrough to 9.2. Excluded items (removal, network submission, change feed, project-config change) have no task. Test tasks follow their implementation tasks (2.4→2.5, 2.6→2.7, 2.8→2.9, 3.1→3.2, 4.2→4.3, 5.1→5.2, 6.1→6.2). The 183 criterion (adding a migration, kind and rows without changing this slice) is forward-looking and cannot be tested in 181.

### [PASS] Parent architecture carries the D4 amendment

Line 152 places the requests initiative index on the member registration ("181 adds the requests initiative index to the member registration (slice 181, D4)"), and line 59 agrees. The task file does not need to amend the parent.

### [CONCERN] Refactor commits contradict the "commit on their own" rule

Line 51 says each refactor commits on its own before any program code. The design's Risk Assessment (design line 431) asks for the three extractions to be "committed on their own". The markers bundle 1.1 with 1.2 (line 68) and 1.4 with 1.5 (line 89). Add markers after 1.1 and 1.4, or change line 51 to name the pairs.

### [CONCERN] Task 9.1's exception list omits the planned edits to existing tests

9.1 allows edits only for the 7.4 column tuples and the 1.4/1.5 moves. Other tasks edit existing test files: 3.4 (tests/inbox/test_inbox_public_api.py), 4.4 (test hosts), 5.3 (tests/test_import_boundaries.py), 7.5 (tests/test_cli_inspect.py, tests/serve/) and 8.2 (tests/test_writer_guard.py). Read literally, 9.1 flags them. List them, or state that additive updates named in their own task are allowed.

### [CONCERN] The walkthrough notes and check-offs may never be committed

9.2 writes what each walkthrough step showed into this file. The commit at line 275 happens only "if Tasks 9.1 or 9.2 changed files". With no code change, the notes and check-offs stay uncommitted. The cadence rules require check-offs and notes to ride in a commit, and forbid a notes-only commit. Decide where the walkthrough record lives (for example, a review document committed under the planning rule) and say so in 9.2.

### [CONCERN] `updated_at` behaviour on re-submission is not specified

2.7 requires an identical re-submission to be "applied with no change but `updated_at` rules", which is not an instruction. 2.6 (line 118) says `updated_at` advances on replace, but not whether an identical body advances it. It also does not say what happens to member rows' `registered_at` and `updated_at` when a replace keeps, removes or re-adds them. `updated_at` is the field 182 uses to date the member list (design line 354), so the rule matters beyond this task. State it in the task or the design before 2.6.

### [CONCERN] Detail text is undefined for two of the five unreadable reasons

5.1 says "Order and detail text per LLD D6". D6 defines a detail for `store_unreadable` (the error), `unlinked` (which links) and `checkout_unresolved` (its reason). It defines none for `store_missing` (design line 190) or `snapshot_missing` (design line 193). D8 requires `reason = "<reason>: <detail>"` on `program-blocked` (design line 215), so the implementer has to invent text. Name the detail for both reasons.

### [CONCERN] The quarantine test does not check that `invalid_payload` names the field

The success criterion at design line 371 requires a hand-written invalid payload to be quarantined with `invalid_payload` naming the field. 4.3 checks that each reason moves the file and writes `.reason.json`. It does not check that the sidecar for `invalid_payload` carries the field name. Add that assertion.

### [NOTE] The dependency on 140 appears in one place and is missing from two

Line 43 names 140 (question and blocked rows) as a dependency. The frontmatter (lines 6–12) does not list 140, and design line 363 says "140: nothing", although the program blocked list reuses 140's blocked rows. Align the three.

### [NOTE] Task 2.6 is the largest store task

2.6 combines the apply transaction (id check and record write), `register_program`'s replace and timestamp rules, three ordered rejections, and the reserved `member_referenced` hook, at effort 4. Splitting it so the transaction shell and create/replace land first would let 2.8 reuse a tested shell. Not required.

### [NOTE] Two small tasks could fold into neighbours

2.1 (effort 1: path constants and two tests) could fold into 2.2 or 2.3. 5.3 (effort 1) could fold into 5.2. The manual mutation check at line 190 (add an `amoeba.runner` import, then revert it) goes beyond what the criterion needs.

### [NOTE] Task 9.2 stops on a missing `sq` without attempting setup

The project rule is that installing declared dependencies is part of the work. If `sq` is a declared dependency (the design says `amoeba start` needs it), 9.2 should attempt installation per the project's setup and write `BLOCKED:` only if that fails.

### [NOTE] "Nothing raises for a member" is not guaranteed once the store has opened

`read_member`'s `StoreError` catch (D6) covers only its own reads. 7.3 then calls `_blocked_rows` on a store that opened, and a `StoreError` there (for example, a busy timeout) is not covered by any step. Say whether it becomes a `store_unreadable` row for that member or is treated as a fault.

### Run Digest

- Response length: 8037 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 529006 / 367161 / 161835 / 71061 / not computed
- Duration: 370.4 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
