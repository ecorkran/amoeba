---
docType: review
layer: project
reviewType: tasks
slice: state-home-and-question-lifecycle
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: baa3887441a0f48676acd62b5dfde2ed0e44265d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 899865
cachedTokens: 712185
cacheWriteTokens: 187666
completionTokens: 78298
durationSeconds: 343.8
costUsd: 0.40394
costBasis: provider
runId: run-20261112-p5-f2bee377
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F003
    severity: pass
    category: verification
    summary: "Named repo paths and symbols exist"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F004
    severity: concern
    category: coverage
    summary: "No load test or CI gate for the concurrency paths"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F005
    severity: concern
    category: coverage
    summary: "The import-boundary test is never updated"
    location: "tests/test_import_boundaries.py"
  - id: F006
    severity: concern
    category: verification
    summary: "`sq runs list --all` is unverified and has no version gate"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:227"
  - id: F007
    severity: concern
    category: correctness
    summary: "\"Absent from the listing means `run_gone`\" assumes the listing is complete"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:260"
  - id: F008
    severity: concern
    category: safety
    summary: "The real-upgrade backup and restore are underspecified"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:395"
  - id: F009
    severity: concern
    category: granularity
    summary: "Three items are too large for one checkbox"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:93"
  - id: F010
    severity: concern
    category: completability
    summary: "The crash-point tests have no named injection seam"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:103"
  - id: F011
    severity: concern
    category: commit-markers
    summary: "The 13.2 commit can contain only notes"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:391"
  - id: F012
    severity: note
    category: sequencing
    summary: "Commit boundaries: section 1 and section 7"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:78"
  - id: F013
    severity: note
    category: verification
    summary: "`member_of_other_program` is not a function in the repo"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:315"
  - id: F014
    severity: note
    category: completability
    summary: "Migration 003's index wording could create duplicate index names"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:131"
  - id: F015
    severity: note
    category: rules-compliance
    summary: "The re-raise in 2.1 has no logging step"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:84"
  - id: F016
    severity: note
    category: testing
    summary: "Two design rules in D8 have no test"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:329"
  - id: F017
    severity: note
    category: scope
    summary: "Scope: the CHANGELOG entry and the pending planning edits"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:400"
---

# Review: tasks — slice 228

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria coverage

Each functional criterion (slice design lines 356-365) maps to a section: legacy move 2.3-2.5; double store and held lock 2.3-2.4; dismiss 6.3-6.4; retract 6.5-6.6; answer limit 4.1-4.2; sweep closures 7.4-7.9; `set_up remove` 10.3-10.4; pruning 11.2-11.3; `wrong_checkout` 8.1-8.2; calls log 9.1-9.4. Technical requirements map to 3.4, 12.2 and 13.1. Integration requirements (every state has an exit) map to 6.8, 7.9 and 13.1. Walkthrough steps 1-8 are 13.2 and step 9 is 13.3.

### [PASS] Sequencing and test-with pattern

Sections run in dependency order: homes (1), move (2), migration 003 (3), limit and precedent (4), store writes (5), dismiss and retract (6), sweep (7), `wrong_checkout` (8), calls log (9), `set_up remove` (10), prune (11), docs (12), validation (13). No cycles. Each implementation item is followed by its test item. No task merges or pushes.

### [PASS] Named repo paths and symbols exist

Confirmed in the repo: the 0.2 inputs (`config/home.py`, `store/migrations.py`, `operations/handle_pause.py`, `status.py`, `decisions.py`, schema `001` and `002` only), the named test helpers and pin tests, `COUNT_AUTOMATIC_ANSWERS`, `SELECT_PM_PRECEDENT`, `check_eligibility` (which polls internally, as 7.6 says), `RUN_POLL_TIMEOUT_SECONDS`, `TERMINATE_GRACE_SECONDS`, `RUNS_LIST_FLAGS`, the `set_up` modules, `CONCEPT_MEMBER_NOT_MEMBER`, and the live pause fixtures. The one mismatch is in the `member_of_other_program` finding below.

### [CONCERN] No load test or CI gate for the concurrency paths

The Python rules (`.claude/rules/python.md`, "Load-test tier") require a load test in `tests/load/` for code on concurrency paths, and CI must gate it. This slice adds racing compare-and-set writers (sweep, answer, dismiss, retract, `set_up remove`), a legacy lock wait under busy timeout, and concurrent calls-log appends. The design also fixes a time bound on `status` (design lines 200 and 344). The tasks have only functional concurrency tests (2.4, 7.5, 9.2, 10.4). `tests/load/` does not exist. I did not read `.github/workflows/ci.yml`, so whether it gates anything is unverified. Add a task that creates a `tests/load/` test with a latency bound for the sweep under concurrent writers and for `status`, plus a CI step that gates it.

### [CONCERN] The import-boundary test is never updated

Design Technical Requirements (line 371) require the import-boundary, home and schema-pin AST tests to be "updated and pass". Tasks cover the home AST test (1.2), the schema pin (3.4) and the store-safety test (2.5, 10.2). Nothing updates `tests/test_import_boundaries.py`, and nothing asserts the rule that `store/relocate.py` imports nothing from `config` (design line 113, task 2.1). Task 0.2 only lists the file. Add a step to 2.1 or 2.2 that extends the import-boundary test to cover `store/relocate.py` and `operations/state_move.py`.

### [CONCERN] `sq runs list --all` is unverified and has no version gate

Task 7.1 adds `--all` to `RUNS_LIST_FLAGS` and says to "update the stub sq and fixtures to honor --all". Nothing confirms the installed `sq` has the flag. Task 0.2 gates only on 0.24.24. The design checks `--all` on 0.24.27 only (design line 200), so the minimum version that has it is unknown. Two fixes: (a) before 7.1, confirm `sq runs list --help` shows `--all` and set the gate at the version that adds it; (b) record the `--all` fixture from real `sq` output. The parser rule in CLAUDE.md requires production-format fixtures. Task 8.2 records real output, but 7.1 does not.

### [CONCERN] "Absent from the listing means `run_gone`" assumes the listing is complete

7.8 closes an open row as `run_gone` when its run is absent from the `--all` listing (design line 200). That can close a question the PM still needs. It is only correct if the listing is complete, and nothing in the task checks for a page or count cap. The design's sample of 100 completed runs does not establish that. Add a step to confirm `--all` is uncapped, for example by comparing it with `poll_run` for a run the listing omits, before 7.8 relies on absence. This is a CONCERN rather than a FAIL because `answer` reopens a closed row (design line 184), so a false closure is recoverable.

### [CONCERN] The real-upgrade backup and restore are underspecified

13.3 backs the production store up to `/tmp/amoeba-pre-228.sqlite3`. `/tmp` is not durable. The move then deletes the legacy store (design D2 step 4), so after 13.3's `amoeba status` the backup is the only copy outside the state home. The task gives no restore procedure and no check that the backup opens. It also runs migration 003 (DROP and ALTER) on production data. CLAUDE.md allows that only for a PM-designated database. The design's step 9 designates it, so the task should cite that. Fix: back up to a durable location under the user's home, run `PRAGMA integrity_check` on the backup, and write the restore steps.

### [CONCERN] Three items are too large for one checkbox

- 2.3 (lines 93-99) combines the lock, copy, verify, rename, both-stores branch, directory moves, `MoveReport` and `open_state_store`. Split it into (a) lock, copy and place (D2 steps 1-4), (b) directory moves and the both-stores branch (step 5 and the set-aside), and (c) `MoveReport` and `open_state_store`.
- 7.8 (lines 259-262) combines `sweep_scope`, three new `StatusResult` fields and a waiting-list rule change. Split it into `sweep_scope` with its write, then the `status` wiring.
- 10.3 (lines 323-328) combines resolve, checks, apply, four problem codes and the change lines. Split it into resolve and apply, then checks and problem codes.

### [CONCERN] The crash-point tests have no named injection seam

2.4 asks for a simulated crash after each of steps 1 to 4, inside step 2, and during step 5. It does not say how to simulate one. 2.2 names a hook for the verify step, and 2.3 names an injectable mover, but nothing covers step boundaries. A junior AI would have to invent the seam. Name it, for example an optional `checkpoint: Callable[[str], None]` on `prepare_state_home` called at each step boundary, with the test raising at a named checkpoint.

### [CONCERN] The 13.2 commit can contain only notes

13.2 records walkthrough results as notes and ends with `test: record the slice 228 walkthrough results`. If every step passes, the commit stages only notes. CLAUDE.md forbids a commit that "only adds notes". Either fold the notes into the 13.4 commit or make this commit carry a real change (for example, the walk test 13.1 adds). The `test:` prefix also does not fit a notes-only commit.

### [NOTE] Commit boundaries: section 1 and section 7

After the section 1 commit, `store_path()` points to the state home while the real store is still in `~/.config/amoeba/`. No code moves it until section 2. The tests pass because of `AMOEBA_HOME`, and the branch is not installed until 13.3, so no harm is done. An install from that commit would still open an empty store. Consider merging sections 1 and 2 into one commit. Section 7 is the largest commit (nine items). A marker after 7.7, where the `handle_pause` sweep works on its own, gives a reviewable working point.

### [NOTE] `member_of_other_program` is not a function in the repo

10.1 says the predicate applies to "the lookups `resolve_member` and `member_of_other_program` use". `resolve_member` is at `src/amoeba/operations/members.py:42`. No function named `member_of_other_program` exists. The name appears only as `SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM`, raised at `src/amoeba/operations/set_up_checks.py:91`. The implementer has to find the real read behind that check, or the 10.2 AST test may not cover it. Name the function that does the lookup.

### [NOTE] Migration 003's index wording could create duplicate index names

131 says to create `questions_new` "with ... the existing columns and indexes" and then "recreate indexes". SQLite index names are unique across the database, so creating indexes on `questions_new` under the existing names fails. Say explicitly: create the table with no indexes, copy, drop, rename, then create the indexes.

### [NOTE] The re-raise in 2.1 has no logging step

2.1 catches `sqlite3.Error` or `OSError`, deletes the target, and raises `StoreRelocateError`. CLAUDE.md requires a re-raise to be preceded by `logger.exception` at ERROR level. Add that to this step and to the verify-failure path.

### [NOTE] Two design rules in D8 have no test

Design D8 says an answered question awaiting a resume does not block removal (design line 259), and removing the concept member without clearing the concept is rejected by `concept_member_not_member` (design line 256). 10.3 mentions both, but no item in 10.4 tests either. Add one test for each.

### [NOTE] Scope: the CHANGELOG entry and the pending planning edits

13.4 adds a CHANGELOG entry. The design does not mention it, though `CHANGELOG.md` exists, so it probably follows repo convention. Keep it if so. The task correctly excludes the design's Pending Planning Edits (design lines 311-316), but nothing tracks them. Until they land, the 226 document still says six operations, and the 220 document is stale. Name who makes those edits so 226 is not built from a stale document.

### Run Digest

- Response length: 12754 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 899865 / 712185 / 187666 / 78298 / not computed
- Duration: 343.8 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
