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
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 4eecc95c13ed5ab6e94a4a307b099fe79c831026
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 285653
cachedTokens: 185135
cacheWriteTokens: 100510
completionTokens: 5256
durationSeconds: 41.5
costUsd: 0.473801
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage across both task files"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, sizing and commit cadence in Sections 1–4"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 7.2 commits in the middle of the 7.1→7.3 commit pair, and 7.1 sits untested behind a PM step"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:150-205"
  - id: F004
    severity: note
    category: consistency
    summary: "The slice design's \"two new kinds\" line is stale; Task 6.4 works around it without correcting it"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:351"
  - id: F005
    severity: note
    category: conventions
    summary: "Several implementation-then-test pairs use a `feat` prefix on the test commit"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:239"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage across both task files

Every Functional and Technical Requirement from the slice maps to a task.
- **D4 refusal:** Tasks 1.2–1.3.
- **Check models and standing table:** Tasks 2.1–2.2.
- **Migration 007 and the 6→7 upgrade:** Tasks 3.1–3.2.
- **Retry rule, non-empty `upstream_version`, negative count:** Tasks 3.3–3.4.
- **Judge samples, D2 consistency and previous-round skip:** Tasks 4.1–4.6.
- **Calibration, with the no-write and no-metrology tests:** Tasks 5.1–5.2.
- **`check` kind and `check_recorded` trigger:** Tasks 6.1–6.4.
- **Ingest, listings and the judge fixture:** Tasks 7.1–7.6.
- **End-to-end test, docs and walkthrough:** Tasks 8.1–8.3.

I found no scope creep. The slice states no NFR, so no load test or CI-gating task is needed.

### [PASS] Sequencing, sizing and commit cadence in Sections 1–4

Each implementation task is followed immediately by its test task. The "committed with Task N.M" notes pair them correctly, and commits fall at every pair rather than at the end. Dependencies are acyclic. The fixture capture is requested in Task 1.1 but consumed only in Task 7.2, so it doesn't block earlier work. I checked the referenced paths and they exist: the 105 stdout fixture, `test_migration_006.py`, `_verdict_writer.py`, `_block_writer.py`, `inbox.py`, `verdicts.py`, and `ExitCode.REVIEW_UNREADABLE = 12`. Task 3.3 is the largest task here (Effort 4), but its contents form one logical unit and are tested together in Task 3.4.

### [CONCERN] Task 7.2 commits in the middle of the 7.1→7.3 commit pair, and 7.1 sits untested behind a PM step

Task 7.1 says "Committed with Task 7.3", but Task 7.2 sits between them and has its own commit step. Two problems follow:
- A repo-root `git add` in 7.2 would sweep in 7.1's untested change, which breaks the stated rule that a commit never holds untested behavior.
- If 7.2 stops to ask the PM for the capture, 7.1 stays uncommitted and untested for an indefinite time.

Suggested fix: reorder to 7.2 (fixture confirmation), then 7.1, then 7.3. Alternatively, give 7.1 and 7.3 a test that uses an existing ordinary fixture, so the pair doesn't depend on the PM capture. Either way, 7.2 should name the files it commits.

### [NOTE] The slice design's "two new kinds" line is stale; Task 6.4 works around it without correcting it

Technical Requirements say the invariant test passes "with the two new kinds". D9 and "Excluded" define only one new kind, `check_recorded`. Task 6.4 notes the conflict and follows D9, which is correct. Nothing in the tasks fixes the slice text, though. Add a one-line step to 8.2 or 8.3 to correct the slice. The walkthrough edit in 8.3 is limited to the walkthrough section, so this needs its own step or a note to the PM.

### [NOTE] Several implementation-then-test pairs use a `feat` prefix on the test commit

Each test task commits together with the behavior it covers (3.4, 4.2 and others), so `feat(...)` is acceptable. Tasks that commit tests alone use `test:` (7.2, 8.1). No change is needed.

### Run Digest

- Response length: 3914 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 285653 / 185135 / 100510 / 5256 / not computed
- Duration: 41.5 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
