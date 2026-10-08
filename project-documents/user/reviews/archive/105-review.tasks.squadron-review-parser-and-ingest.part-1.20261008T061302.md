---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: deda74ce568821093adce58148a7d32cda716340
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 41.8
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-392"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit cadence"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:28"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 8.2 commits an interim state where ingest reports `OK` without submitting"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:175"
  - id: F004
    severity: concern
    category: risk
    summary: "Task 1.2 is an external-dependency gate with a large downstream blast radius"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:68-92"
  - id: F005
    severity: note
    category: coverage
    summary: "Task 4.2's trailing-line test differs from the design's criterion"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:343"
  - id: F006
    severity: note
    category: scoping
    summary: "Several tasks are large but acceptable"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:288-309"
  - id: F007
    severity: note
    category: process
    summary: "Task 9.3 edits the slice design file"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:357"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

- **Parser behavior:** file fixtures are covered by Tasks 3.3/3.5, and stdout captures, the `fallback_used` branches, and `requested_model` by 4.2. File/stdout key equality is in 4.2.
- **Record id:** hand-edit invariance is in 5.2.
- **Composition:** the D4 cases are in 5.4.
- **Error cases:** each listed error raises in 3.5, 4.2, and 5.4. `provider_failure_problem` is pinned in 2.3.
- **Dependency rules:** the import-direction rule and the single definition of Squadron keys are asserted by Task 5.5.
- **Payload round trip:** Tasks 6.1/6.2.
- **Test migration:** Tasks 7.1–7.4.
- **Ingest command:**
  - Failure paths and the no-store refusal are in 8.3.
  - The success path, the D7 slice mismatch, and the stderr output are in 8.5.
  - The running, stopped, and `kill -9` scenarios are in 8.6/8.7. The unknown project is in 8.7.
  - The stdout/file pair is in 8.8.
- **Docs and walkthrough:** Tasks 9.1–9.3.

No scope creep found. The extra tests in 5.5 and 8.1 trace to the Technical Requirements.

### [PASS] Sequencing, test-with pattern, and commit cadence

- Every implementation task is committed together with the test task that follows it: 3.2/3.3, 3.4/3.5, 5.1/5.2, 5.3/5.4, 8.2/8.3, and 8.4/8.5.
- Commits are spread across all nine sections, not batched at the end.
- Moving PyYAML to runtime first (Task 2.1) satisfies the parser's import need.
- Task 7.4 deletes the old fixture reader only after 7.1–7.3.
- Task 7.2 correctly notes that `test_finding_changes.py` imports no removed helpers. A grep of `tests/` confirms only four files use them: `review_fixtures.py`, `test_demo_evidence_payloads.py`, `test_finding_identity.py`, and `evidence_harness.py`.

### [CONCERN] Task 8.2 commits an interim state where ingest reports `OK` without submitting

Task 8.2 ends with a `TODO(8.4)` stub that returns `OK` after step 5, and the commit "covers 8.2 and 8.3". Task 8.3 tests only failure paths, so that commit ships a command that reports success while doing nothing. The project rules say never to use silent fallback values. Either have the stub fail explicitly, for example with a nonzero `ExitCode` or `NotImplementedError`, until 8.4. Or merge 8.2 and 8.4 (about 5 effort points together) and keep 8.3/8.5 as the tests.

### [CONCERN] Task 1.2 is an external-dependency gate with a large downstream blast radius

Task 1.2 needs `sq`, a provider key, and network access, and its stop conditions rightly forbid hand-building a pair. Four later tasks depend on its output: 3.5 (new file stamp and `sq_run_id` case), 4.2 (pair equality), 5.2 (file versus stdout ids), and 8.8 (end-to-end). A blocked 1.2 therefore stalls work in Sections 3–5 and 8.
- Add a note that if 1.2 is blocked, the dependent assertions are deferred to a follow-up. Alternatively, move 1.2 later, since 1.1 and 1.3 already cover most parser tests.
- The `sq review slice 105` step also uses a slice design that will change as the review runs. The note about recording the actual version covers this, but the `sq` run and the PM stop condition should stay visible.

### [NOTE] Task 4.2's trailing-line test differs from the design's criterion

The slice design says "The 0.14.0 captures, which have a trailing stdout line, parse the same as a pure-JSON capture." The task instead builds the case by appending a `Saved review to` line, noting that no existing capture has one. That is correct: `tests/fixtures/README.md:86` confirms the 104 capture has no trailing line. The criterion is still satisfied, but the design's wording is inaccurate and could be corrected in a later pass.

### [NOTE] Several tasks are large but acceptable

Tasks 3.5, 4.2, and 8.6 each pack many cases (effort 3). Each case is enumerated and independent, so a junior AI can work through them, and splitting would add churn without benefit. Task 5.5 is small but cohesive.

### [NOTE] Task 9.3 edits the slice design file

The only file modified is the LLD itself, to replace the draft walkthrough with real output. This is intentional, and the "do not edit the LLD to match" rule is explicit. It is fine as long as the edit is limited to the Verification Walkthrough section.

### Run Digest

- Response length: 5474 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 41.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
