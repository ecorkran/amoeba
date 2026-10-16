---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: e1d46dc185b3fd5378bdcf7c50965a0aa5091a1c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 8
promptTokens: 380089
cachedTokens: 278564
cacheWriteTokens: 101515
completionTokens: 5227
durationSeconds: 40.9
costUsd: 0.486876
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage across files 1 and 2"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task 8.1 duplicates coverage already pinned in 1.5 and 4.4"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md (Task 8.1, steps 4–5)"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 5.2 sends the junior to sources that do not hold the metrology strings"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md (Task 5.2, no-metrology test step)"
  - id: F005
    severity: concern
    category: clarity
    summary: "Task 7.4 has a conditional step the junior can't resolve from the task"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md (Task 7.4, last step)"
  - id: F006
    severity: note
    category: proportionality
    summary: "Task 6.4 mutation-proof step is fiddly"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md (Task 6.4, second step)"
  - id: F007
    severity: note
    category: scope
    summary: "Issue #2 closure is deferred to the PM"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md (Task 8.3, last step)"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage across files 1 and 2

Each file-2 criterion maps to a task:
- Calibration, with its no-write and no-metrology constraints, maps to 5.1–5.2.
- The `check` kind, including validation rejection, quarantine of unknown outcome words, replay and the CLI flags, maps to 6.1–6.2.
- The `check_recorded` trigger, the invariant extension and the one-change-per-check rule map to 6.3–6.4.
- The sample id on ingest, the `verdicts` column and option, and the `checks` and `calibration` listings map to 7.1–7.5.
- The end-to-end test, the contract docs, the CHANGELOG and the validation walkthrough map to 8.1–8.3.

File 1 covers the remaining criteria:
- D4 refusal
- D2 consistency check
- previous-round skip
- migration upgrade
- standing table
- retry and WARNING behaviour
- progress records

No NFR is restated in the slice, so no load test or CI gating task is needed.

### [PASS] Sequencing and commit cadence

Dependencies are linear and acyclic. Implementation and test tasks are committed together as pairs: 5.1/5.2, 6.1/6.2, 6.3/6.4, 7.1/7.2 and 7.4/7.5. Tasks 7.3, 8.1 and 8.2 commit on their own. The deliberately failing intermediate states (the 103 completeness test after 6.1, 106's invariant test after 6.3) are called out, with an instruction not to commit between the paired tasks. The paths the tasks reference all exist in the repo.

### [CONCERN] Task 8.1 duplicates coverage already pinned in 1.5 and 4.4

The slice's end-to-end requirement is one flow: ingest a sample, submit two more samples and a check, `kill -9`, `start`, then inspect. Two further steps go beyond it:
- The wrong-review-type rejection is already tested through the inbox in Task 4.4.
- The `--stdout-json` exit-12 refusal with an empty `inbox/new/` is already tested at the CLI in Task 1.5.

Both add subprocess-level cost for no new criterion. Drop them from 8.1 or merge them into the walkthrough only. The walkthrough already runs both (steps 3 and 5).

### [CONCERN] Task 5.2 sends the junior to sources that do not hold the metrology strings

The step says to take "the two strings from the LLD and the 104 notes". The LLD names only "Squadron's metrology directory or config key" and gives no literal. The 104 notes are not identified. The only literals in the repo are in the planning notes: `metrology/` in `user/notes/002-upstream-delta.amoeba.md:121` and `metrology.min_evidence_n` in the same line. The step does say to ask the PM if the key can't be found, which avoids a guess. Even so, the task will reliably stall. Name the source file and line in the task, or have the PM confirm the strings before this task starts.

### [CONCERN] Task 7.4 has a conditional step the junior can't resolve from the task

"Add `inspect_checks.py` to the module list in `tests/test_import_boundaries.py` if that list exists for string-constant checks." The file exists, but the task doesn't say which list or what condition applies. Either name the list or drop the conditional. The "or wherever `LISTINGS` names are pinned" wording for the registry test has the same weakness. `tests/inbox/test_listings.py` exists and is the likely target.

### [NOTE] Task 6.4 mutation-proof step is fiddly

Running the invariant test once against a copy of the migration without the trigger, then discarding the copy, risks leaving a stray file behind. It does satisfy the slice's "fails if the trigger is missing" requirement. A temporary monkeypatch or fixture in the test itself would be cleaner. This is optional.

### [NOTE] Issue #2 closure is deferred to the PM

The slice's Technical Requirements say issue #2 "is closed". The task closes it only if the PM instructs, and otherwise lists it as pending. This is correct, since closing an issue is outward-facing. The slice and task wording differ, but no change is needed.

### Run Digest

- Response length: 4974 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 380089 / 278564 / 101515 / 5227 / not computed
- Duration: 40.9 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
