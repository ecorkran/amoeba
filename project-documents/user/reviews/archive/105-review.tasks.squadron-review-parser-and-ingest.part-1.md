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
reviewedSha: fbae199af97cea673217422c64abbbdda502397a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 46.5
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-390"
  - id: F002
    severity: pass
    category: process
    summary: "Test-with pattern, commit cadence and no-NFR handling"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:28"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Docs tasks are chained behind the externally gated, possibly blocked pair task"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:326"
  - id: F004
    severity: concern
    category: clarity
    summary: "Fixture file names for the 102 rounds are ambiguous"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:256"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Provider-failure standing is asserted only in the end-to-end test"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:299"
  - id: F006
    severity: concern
    category: enforcement
    summary: "\"Defined once\" for `provider_failure_problem` is verified by manual grep only"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:155"
  - id: F007
    severity: note
    category: consistency
    summary: "Stale LLD wording about the 0.14.0 stdout captures is handled but not reconciled"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:345"
  - id: F008
    severity: note
    category: sequencing
    summary: "Minor dependency declarations"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:125"
  - id: F009
    severity: note
    category: scope
    summary: "Task sizing is appropriate"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:268"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage is complete

Every functional and technical criterion maps to a task:
- **Parser file/stdout mapping:** 3.4/3.5, 4.1/4.2.
- **`findings_parsed` branches:** 4.2.
- **`requested_model` rule:** 4.2.
- **Record id stability:** 5.1/5.2.
- **Version rule (D4):** 5.3/5.4.
- **Import direction and single key definitions:** 5.5.
- **Payload round trip:** 6.2.
- **Test migration:** 7.1–7.4.
- **Ingest failure paths, success path, running/stopped process, unknown project:** 8.3, 8.5, 8.6, 8.7.
- **Pair equality and the D5 consequence:** 4.2 and 8.8.
- **Docs:** 9.1/9.2.

I found no scope creep. The only extras are test-support items such as 8.1's exit-code uniqueness test and 8.3's `Store`-import check, and both trace to D6 and the exit-code requirement.

### [PASS] Test-with pattern, commit cadence and no-NFR handling

Each implementation task is followed immediately by its test task (3.2→3.3, 3.4→3.5, 5.1→5.2, 5.3→5.4, 8.2→8.3, 8.4→8.5), and commits are paired explicitly. Commits are spread across all nine sections, not batched at the end. The slice states no NFR, so no `tests/load/` task or CI gate is required. Task 9.3 runs `tests/load` for regressions only, and that directory exists.

### [CONCERN] Docs tasks are chained behind the externally gated, possibly blocked pair task

Task 1.2 is contained as an external gate, and Tasks 3.5, 4.2, 5.2 and 8.8 have their pair-dependent items separated out. But Task 9.1 depends on Task 8.8, which is wholly pair-dependent. If 1.2 is blocked, 9.1 → 9.2 → 9.3 are blocked by the stated dependency chain. That undercuts the "carry on with everything not pair-dependent" intent. Make 9.1 depend on 8.7. Keep 8.8 as an explicit input to 9.3, which already checks for `blocked on 1.2` items. Task 9.1 also documents the D5 "two records" consequence, which 8.8 only demonstrates. That is acceptable, since the consequence is stated in the LLD.

### [CONCERN] Fixture file names for the 102 rounds are ambiguous

`tests/fixtures/sq_reviews/` holds both timestamped and un-timestamped 102 files: `part-1.20260921T112529.md` and `part-1.md`, and `part-2.20260921T112635.md` and `part-2.md`. The tasks mix descriptions with partial names:
- 3.3 says "`102-…part-2.md` (round 2)" and "the round 1 part 1 file".
- 3.5 says "the 0.14.0 `102-…part-2.md`".
- 8.6 says "round 2 part 1 (`102-…part-1.md`)" and "the round 2 part 2 provider-failure file".

A junior AI could pick the wrong variant, or the wrong round, and the expected values would then silently differ. Name each file in full once, or reference the `ROUND_*` constants from `tests/review_fixtures.py`, which the task file says is the single home for paths. The stdout capture names in 4.1/4.2 are also hard-coded strings and should use constants.

### [CONCERN] Provider-failure standing is asserted only in the end-to-end test

The LLD's criteria require both provider-failure files to parse with "standing `provider_failure`". Task 3.5 asserts `provider_failure=True` and no findings, but not the standing, which the store computes. Task 8.6 checks standing only for the 102 round-2 provider-failure file. The 928 file's standing and the 925 file's `unparsed` standing are checked only in the walkthrough (9.3), which is a manual run. Add a standing assertion for 928 and 925 in a parser-to-standing test, or in 8.6.

### [CONCERN] "Defined once" for `provider_failure_problem` is verified by manual grep only

The success criterion "message texts appear once in `src/`" (Task 2.2) is a manual check. The LLD calls `provider_failure_problem` the only definition of the rule. Task 5.5 already enforces the same discipline for key names via `ast`. Extending it, or adding a small test, to assert that the two message strings appear once under `src/` would protect the invariant after this slice.

### [NOTE] Stale LLD wording about the 0.14.0 stdout captures is handled but not reconciled

Task 4.2 correctly tests trailing-line tolerance synthetically. It notes that the LLD's claim (that the 0.14.0 captures carry a trailing stdout line) contradicts the fixtures README. The commit message will record the difference, but the design is left stale. Task 9.3 forbids edits outside the Verification Walkthrough. Consider asking the PM to correct the LLD criterion, so the verification step doesn't mismatch it.

### [NOTE] Minor dependency declarations

- Task 2.1 lists "None" as its dependency but also says the branch from Task 1.1 exists. Declare the dependency on 1.1, or move branch creation to a standalone first step.
- Task 6.1 depends on 5.5, and 8.1 also depends on 5.5. Neither needs the import-direction test, so they could start after 5.4. This is harmless, but it serializes work that is independent.
- The 8.2 interim stub returns `SUBMISSION_REFUSED` and is committed with 8.3. This is sound, since 8.3 asserts only failure paths, and the guard against returning `OK` is explicit.

### [NOTE] Task sizing is appropriate

Tasks 3.4 and 8.3 are the largest (effort 3, many enumerated cases), but each has one objective and a checklist. They are splittable if the junior struggles, but I don't recommend splitting up front. Tasks 2.3 and 5.5 are small but coherent. Merging them into their neighbours would break the test-with pairing.

### Run Digest

- Response length: 6672 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 46.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
