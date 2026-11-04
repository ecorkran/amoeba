---
docType: review
layer: project
reviewType: tasks
slice: edges-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/183-tasks.edges-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 1652ae13d2fc9211e4c83542f13c00d80b829ef0
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 647013
cachedTokens: 501177
cacheWriteTokens: 145824
completionTokens: 52424
durationSeconds: 287.3
costUsd: 0.166363
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "Slice with no CF name has no test for branch_head_missing"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:154"
  - id: F002
    severity: concern
    category: verification
    summary: "Verification step 1 names a test file no task creates"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:267"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Readiness regression baseline is not captured before the change"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:142"
  - id: F004
    severity: concern
    category: sizing
    summary: "Task 7.2 bundles too much for one pass"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:203"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Task 7.7 is too large and repeats coverage from 7.3"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:226"
  - id: F006
    severity: note
    category: proportionality
    summary: "Load test in 8.3 goes beyond the stated criteria; CI gating already exists"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:242"
  - id: F007
    severity: note
    category: status
    summary: "Task 0.1 will block until 181 merges"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:63"
  - id: F008
    severity: note
    category: accuracy
    summary: "Two paths are imprecise"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:118"
  - id: F009
    severity: note
    category: accuracy
    summary: "Exit code 9 for a missing flag is unverified"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:105"
  - id: F010
    severity: note
    category: consistency
    summary: "Design and task disagree on where release confirmation is written"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:106"
  - id: F011
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:402"
  - id: F012
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies, existing-code references and commit markers hold"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:61"
---

# Review: tasks — slice 183

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Slice with no CF name has no test for branch_head_missing

The design criterion (slice design line 417) says only a read that succeeds without the branch, or a slice with no name, waits `branch_head_missing`. Task 5.2 describes the no-name case as `missing` true with a detail, but none of its tests, and none in 5.3 or 5.4, exercise it. Task 3.2's round-trip covers three `BranchHead` shapes (commit, missing, failed read) and omits missing-with-no-name. Add a helper test in 5.2, and an edge test in 5.3 or 5.4 showing the row lands with `branch` null and the edge waits `branch_head_missing`.

### [CONCERN] Verification step 1 names a test file no task creates

Task 9.2 runs walkthrough steps 1 to 4 and 6. Step 1 (slice design line 440) cites `tests/process/test_program_inbox.py`. No 183 task creates or extends that file, and 181's tasks create `tests/process/test_program_inbox_tenant.py` (181 tasks line 179). As written, step 1 fails on a missing path. Step 2's `-k "waiting or external"` selects by test name, but no task names test functions with those words. Correct the walkthrough path to the real files, and have Task 4.1 name its tests so the `-k` filter selects them.

### [CONCERN] Readiness regression baseline is not captured before the change

Task 4.1 requires the tick to match "a run recorded at the unchanged commit", but does not say to record it before editing `predecessors.py`. Once the readiness change is in, the baseline cannot be recorded from the same tree. The task should say to record the literals first. Task 7.4 also runs a no-edge regression over three configurations. Keep one baseline, or state that the two cover different things.

### [CONCERN] Task 7.2 bundles too much for one pass

Effort 5. The task changes the stage's result type to `ProgramView`, adds the D9 closing pass, adds the observe loop with write-on-change and the budget stop, computes `waiting`, and carries seven tests. Split it into (a) `ProgramView`, the `waiting` and `providing` sets and the D9 closing pass, with its tests, and (b) the observation loop with writes, the budget stop and "unchanged writes nothing", with its tests.

### [CONCERN] Task 7.7 is too large and repeats coverage from 7.3

Effort 5, with nine variant bullets and about twelve scenario tests. The crash after each of release's three writes is tested in 7.3 (line 209) and again at scenario level in 7.7 (line 227). The "no change writes nothing" check appears in 7.2, 7.7 and 8.3. Keep the scenario-level crash tests, since they cover the integration criterion (slice design line 413), and drop the duplicate in 7.3. Alternatively, split 7.7 into a release-variants task and a head-read-and-by-hand task.

### [NOTE] Load test in 8.3 goes beyond the stated criteria; CI gating already exists

The slice design has no numeric load requirement. Its only cost statement is "Cost per tick" (slice design line 509). The 180 architecture documents do not restate a load NFR; the tick-deadline NFR is in the 120 documents and is already covered by `tests/load/test_runner_tick_load.py`, which 9.1 runs. The new case is gated by the existing CI step `uv run pytest tests/load` (`.github/workflows/ci.yml:53-54`), so no CI wiring task is needed. Decide whether slice design line 509 counts as the NFR. If it does, keep 8.3. If not, cut it and keep the no-change-writes assertion in 7.2.

### [NOTE] Task 0.1 will block until 181 merges

181's code is not on the target. `src/amoeba/program/`, `store/program_schema/`, `inspection/program.py` and `tests/load/test_program_load.py` do not exist. Task 0.1 will write `BLOCKED:` as it directs. This is a dependency wait, not a defect in the breakdown.

### [NOTE] Two paths are imprecise

Task 3.1 says "mirror `test_migration_015.py` if present, else `test_migration_010.py`". `tests/store/test_migration_015.py` exists, so drop the hedge. Task 7.4 says "use `tick_rig.py`" with no path. The helper is `tests/runner/dispatch/tick_rig.py` (line 213), not under `tests/runner/`.

### [NOTE] Exit code 9 for a missing flag is unverified

181's task (line 162) sets exit 9 (`SUBMISSION_REFUSED`) for an invalid body. Task 2.1 extends that to a missing `--edge-id`, which may go through argparse's own path. Confirm against the 181 CLI when it lands, or state the code only for an invalid body.

### [NOTE] Design and task disagree on where release confirmation is written

The design's component table lists `confirm_release` in `store/program_edges.py`. No task creates it. Task 2.2 writes `release_confirmed_at` inside `apply_submission`, which matches D4 and the writer split in State Management. Remove `confirm_release` from the table, or add it to 2.2. Task 2.2 is the more specific instruction, so the table is the thing to change.

### [PASS] Success criteria are covered by tasks

Each functional criterion (lines 406 to 418), technical criterion (422 to 426) and integration criterion (430 to 431) maps to a task, except the no-name gap above. Specific traces: wait precedence (6.1), from-source reachability including squash and deleted-branch cases (6.3), release crash points (7.3, 7.7), `member_referenced` (1.6), `program-blocked` (8.1), the locality proof (8.2), and docs and CHANGELOG (8.4 to 8.6, 9.3). No task traces to nothing. The scope-adjacent items, the branch-name helper (5.1) and the import rule (4.1), trace to D5 and the architecture principle.

### [PASS] Sequencing, dependencies, existing-code references and commit markers hold

Groups run 1 to 9 with no forward or circular references, apart from the planned `frozenset()` placeholders that Tasks 7.4 and 5.3 replace. Each implementation task carries its tests inline. The 16 `**Commit**:` markers sit at group ends, after tested code. The frontmatter dependency list matches the slice design, and 182 is correctly left out. These names and files exist as the tasks use them: `is_ancestor_args` (`src/amoeba/runner/git_read.py:90`), `SUBCOMMAND_LOG` (`git_read.py:27`), `read_target` (`src/amoeba/runner/dispatch/checkout_reads.py:128`), `parse_slice_stem`, `ANSWER_DECISION = "resume"` (`src/amoeba/store/question_models.py:40`), `COUNT_ANSWERER_ANSWERS_IN_RUN` (`src/amoeba/store/sql_questions.py:119`), `STORE_FAILURES` (`src/amoeba/runner/faults.py:93`), `tests/runner/git_repo.py`, `tests/runner/purity.py`, `tests/contract/oracle.py`, `tests/store/test_migration_015.py`, and `.claude/rules/python.md` and `sql.md`.

### Run Digest

- Response length: 9074 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 647013 / 501177 / 145824 / 52424 / not computed
- Duration: 287.3 s
- Cost: $0.17 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
