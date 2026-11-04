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
reviewedSha: 39ca4a24fec8c99521f95b23a893553428bcd4c1
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
effort: xhigh
turns: 33
promptTokens: 1305715
cachedTokens: 1123616
cacheWriteTokens: 182079
completionTokens: 72284
durationSeconds: 312.2
costUsd: 0.312921
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every slice-design success criterion maps to at least one task"
    location: "project-documents/user/tasks/181-tasks.program-record.md:1"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies, and commit markers hold"
    location: "project-documents/user/tasks/181-tasks.program-record.md:57"
  - id: F003
    severity: pass
    category: design-consistency
    summary: "The parent documents already carry the requests-index change"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:53"
  - id: F004
    severity: pass
    category: sizing
    summary: "Task count and granularity fit the slice"
    location: "project-documents/user/tasks/181-tasks.program-record.md:57"
  - id: F005
    severity: concern
    category: load-testing
    summary: "No load test exercises the new program inbox drain or the program read in the tick"
    location: "project-documents/user/tasks/181-tasks.program-record.md:277"
  - id: F006
    severity: concern
    category: commit-process
    summary: "The walkthrough's closing check-off has no commit when no fix is needed"
    location: "project-documents/user/tasks/181-tasks.program-record.md:288"
  - id: F007
    severity: concern
    category: commit-process
    summary: "The `fix:` commit in Task 9.2 conflicts with the Fixes rule"
    location: "project-documents/user/tasks/181-tasks.program-record.md:290"
  - id: F008
    severity: concern
    category: test-plan
    summary: "The Task 9.1 exemption list omits test files that other tasks extend"
    location: "project-documents/user/tasks/181-tasks.program-record.md:278"
  - id: F009
    severity: note
    category: conventions
    summary: "Task 2.1 leaves a conditional the code already settles"
    location: "project-documents/user/tasks/181-tasks.program-record.md:101"
  - id: F010
    severity: note
    category: accuracy
    summary: "Task 1.5 names the wrong caller for the path rule"
    location: "src/amoeba/runner/project_config.py:57-61"
  - id: F011
    severity: note
    category: conventions
    summary: "Task 1.1 keeps a default the new parameter should drop"
    location: "src/amoeba/store/migrations.py:123"
  - id: F012
    severity: note
    category: design-consistency
    summary: "Task 7.3 adds a `store_unreadable` path the design does not state"
    location: "project-documents/user/tasks/181-tasks.program-record.md:234"
  - id: F013
    severity: note
    category: testing
    summary: "The inbox path's exit-as-store-failure criterion has no direct test"
    location: "project-documents/user/tasks/181-tasks.program-record.md:179"
  - id: F014
    severity: note
    category: design-consistency
    summary: "The slice design names two different return types for `read_member`"
    location: "project-documents/user/slices/181-slice.program-record.md:109"
---

# Review: tasks — slice 181

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every slice-design success criterion maps to at least one task

Each criterion has a task. Registration and inspection: 2.5–2.10, 3.x, 4.x, 7.1. Payload refusals and quarantine: 3.1–3.3, 3.5, 4.3. Each rejection code except reserved `member_referenced`: 2.7–2.10. Replace, upsert, and idempotence: 2.5, 2.6, 2.10. Blocked reasons and "nothing exits": 5.1, 5.2, 7.3. Stage placement and the no-program regression: 6.1, 6.2. Store failures and `STARTUP_FAILED`: 4.1, 4.3, 6.2. Locality proof and negatives: 8.1. Writer guard and import rules: 5.2, 8.2. Docs and CHANGELOG: 8.3–8.6. Walkthrough steps 1–5: 9.2.

### [PASS] Sequencing, dependencies, and commit markers hold

All of Section 1 precedes program code, and each refactor has its own marker. The dependencies run forward in file order: 2.3 uses `store/connection.py` from 1.2; 3.x uses `validate_repo_relative_path` from 1.5; 4.2 uses the drain from 1.3 and the parser from 3.3; 4.4 precedes the stage in 6.1; 5.1 uses `resolve_checkout` after its move in 1.4. There are no cycles. Each implementation task is followed by its test task. Markers sit at tested points (lines 64–290). Sections 8.3–8.6 have no marker and ride the 9.1 commit, which the rules allow.

### [PASS] The parent documents already carry the requests-index change

Slice design D4 says both parents must be amended. Both already say it: the architecture's principle at line 53 puts the index on the member registration, and the plan's configuration note at `project-documents/user/architecture/180-slices.program-coordination.md:152` says 181 adds it there. The task file's `projectState` claim is accurate, and no parent-amendment task is needed.

### [PASS] Task count and granularity fit the slice

There are 41 tasks in one file, in nine sections that follow the design's build order. Each task maps to one design component or one test surface. Tasks 4.3 and 7.3 carry the most test cases, but each is one test file and one concern. Neither needs splitting, and the file does not need to become several files.

### [CONCERN] No load test exercises the new program inbox drain or the program read in the tick

`.claude/rules/python.md` requires at least one load test for code on the concurrency path. Task 4.2 adds a tenant that drains the program inbox inside the resident process. Task 6.1 adds a program-store read on every tick. Task 9.1 re-runs only `test_runner_tick_load.py` (a `RunnerTenant` tick) and `test_inbox_concurrent.py` (project submissions only), and neither can reach program code. Add a load test under `tests/load/` that drives concurrent program submissions through `ProgramInboxTenant`, plus a tick case with a program store holding the project's program, with latency or throughput bounds. CI already runs `uv run pytest tests/load` (`.github/workflows/ci.yml:54`), so the new file is gated with no new CI task.

### [CONCERN] The walkthrough's closing check-off has no commit when no fix is needed

Task 9.2 is the last task in the file. Its text says that without a fix, "the check-off commits with the next commit on the branch," but none follows. The only later step is the Phase 7 merge, and a check-off may not be committed alone. The walkthrough's check-off would stay uncommitted at the end of Phase 6. Move 9.2 above the 9.1 marker so its check-off rides the `docs:` commit, and run the full checks after any walkthrough fix.

### [CONCERN] The `fix:` commit in Task 9.2 conflicts with the Fixes rule

The project rules say work committed as `fix:` follows the fixes path, not the slice workflow, and that a bug in the slice's own code is part of the slice. A walkthrough correction to the program record's own code is slice work. As written, the marker puts a `fix:` commit on the slice branch. Commit it with the slice's type for the code it changes (`feat:` or `test:`).

### [CONCERN] The Task 9.1 exemption list omits test files that other tasks extend

Task 9.1 allows existing-test edits only for Tasks 1.4, 1.5, 3.4, 4.4, 7.4, 7.5, 8.1 and 8.2. Task 2.1 adds tests to `tests/test_paths.py`, and Task 4.1 adds to the `ProjectStores` tests in `tests/process/` (`test_project_stores.py`). Task 3.5 extends `tests/cli/`, where `test_submit.py` already exists. Read literally, the success check fails on planned work. Add these tasks to the list, or reword it to "no existing test is edited or weakened; new tests may be added to existing files."

### [NOTE] Task 2.1 leaves a conditional the code already settles

Task 2.1 says to reuse the outcome enum "if its values are `applied` and `rejected`." They are: `SubmissionOutcome` in `src/amoeba/store/inbox_models.py:51-55` has `APPLIED = "applied"` and `REJECTED = "rejected"`. Name it directly so the implementer does not have to decide.

### [NOTE] Task 1.5 names the wrong caller for the path rule

The task says `rules_paths` calls the validator. In the code, the rule is an `AfterValidator(_checked_rules_path)` on the `RulesPath` annotation (lines 57–61). `rules_paths` is only the field at line 107. Tell the implementer to change the validator on the annotation, not a function named `rules_paths`.

### [NOTE] Task 1.1 keeps a default the new parameter should drop

`migrate` already takes `expected_version`, but with the default `EXPECTED_SCHEMA_VERSION`. Task 1.1 says to pass the version in and does not say to drop the default. Without that, a new store line that omits the argument silently gets version 15. Remove the default so each caller states its version.

### [NOTE] Task 7.3 adds a `store_unreadable` path the design does not state

Task 7.3 says a `StoreError` from a member's blocked-row read becomes a `store_unreadable` row. D6 limits `store_unreadable` to the reads inside `read_member`, and D8 says blocked rows come from `_blocked_rows` unchanged. The behavior fits the "nothing exits" criterion and is sensible, but the design should carry it. Add it to D8 so the design and the task agree.

### [NOTE] The inbox path's exit-as-store-failure criterion has no direct test

The slice criterion says a program store failure during the program inbox apply exits the process as a store failure. Task 4.3 asserts the re-raise, the counter and the parking. Task 6.2 asserts the process exit, but only for the stage. Add the same process-level exit assertion to 4.3.

### [NOTE] The slice design names two different return types for `read_member`

The component table says `read_member(...) -> MemberState`. D6 (line 186) and Task 5.1 say `Readable | Unreadable(reason, detail)`. The task follows D6, which is correct. Fix the table so the design has one name.

### Run Digest

- Response length: 10226 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 33
- Tokens — prompt / cached / cache write / completion / reasoning: 1305715 / 1123616 / 182079 / 72284 / not computed
- Duration: 312.2 s
- Cost: $0.31 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

- [pass] Every slice-design success criterion maps to at least one task: no change.
- [pass] Sequencing, dependencies, and commit markers hold: no change.
- [pass] The parent documents already carry the requests-index change: no change.
- [pass] Task count and granularity fit the slice: no change.
- [concern] No load test exercises the new program inbox drain or the program read in the tick: added Task 6.3 (`tests/load/test_program_load.py`, concurrent program submissions through `ProgramInboxTenant` plus a tick case with a program store, bounds measured first) and added the file to Task 9.1's explicit load run. CI already runs `tests/load`.
- [concern] The walkthrough's closing check-off has no commit when no fix is needed: moved the CHANGELOG from Task 8.6 to a final Task 9.3 with its own `docs:` marker after the walkthrough, so Task 9.2's check-off rides that commit. This keeps docs and checks committed before 9.2, so a missing `sq` gates only the CHANGELOG, not the earlier work. Chosen instead of moving 9.2 above the 9.1 marker, which would bring back the earlier concern that unrelated work waits on `sq`.
- [concern] The `fix:` commit in Task 9.2 conflicts with the Fixes rule: the conditional marker now uses the slice's type (`feat:`, or `test:` when only tests changed), and 9.2 says to re-run Task 9.1's checks after any fix.
- [concern] The Task 9.1 exemption list omits test files that other tasks extend: reworded to "no existing test skipped, weakened or edited to pass, apart from the moves and edits Tasks 1.4, 1.5, 3.4, 4.4, 7.4, 7.5, 8.1 and 8.2 name; tests added to existing files are not edits".
- [note] Task 2.1 leaves a conditional the code already settles: names `SubmissionOutcome` from `store/inbox_models.py` directly.
- [note] Task 1.5 names the wrong caller for the path rule: now says the `AfterValidator` on the `RulesPath` annotation calls the new validator with `glob_allowed=True`.
- [note] Task 1.1 keeps a default the new parameter should drop: the generalized runner takes the migrations package and expected version as required parameters with no default. `migrate(connection, expected_version=EXPECTED_SCHEMA_VERSION)` stays as the project store's thin wrapper, because many existing tests call `migrate(connection)` and Task 1.1 requires them unedited.
- [note] Task 7.3 adds a `store_unreadable` path the design does not state: added the behavior to D8 of `user/slices/181-slice.program-record.md`; Task 7.3 already matches it.
- [note] The inbox path's exit-as-store-failure criterion has no direct test: Task 4.3 now asserts, through `tests/host_harness.py`, that a program store failure in the program inbox apply exits the resident process as a store failure.
- [note] The slice design names two different return types for `read_member`: the design's D6 now says `-> MemberState` with `MemberState = Readable | Unreadable(reason, detail)`, matching the component table and slice 183's use of the name; Task 5.1 defines that alias.

No finding was deferred, so no GitHub issue was filed.
