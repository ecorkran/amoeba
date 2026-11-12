---
docType: review
layer: project
reviewType: tasks
slice: state-home-and-question-lifecycle
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: b10bcc24c504837855618c70e9d69163a5efb753
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
effort: xhigh
turns: 13
promptTokens: 824545
cachedTokens: 605039
cacheWriteTokens: 219494
completionTokens: 101226
durationSeconds: 457.4
costUsd: 0.487753
costBasis: provider
runId: run-20261112-p5-f2bee377
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: fail
    category: design-rule
    summary: "An answered question whose resume was refused at the run's own pause has no exit, and member removal strands it"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:259"
  - id: F002
    severity: concern
    category: operator-walkthrough
    summary: "A split `XDG_STATE_HOME` between the hook and the shell silently hides the store"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:159"
  - id: F003
    severity: concern
    category: correctness
    summary: "The move checks the legacy file before taking the lock, so a racing process can open a store that was just deleted"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:97-98"
  - id: F004
    severity: concern
    category: safety
    summary: "The real upgrade in §13.3 needs the PM's explicit designation under the production-database rule"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:436"
  - id: F005
    severity: concern
    category: sequencing
    summary: "§13.2 forbids the real-home reads that walkthrough step 2 requires, and the backup comes too late"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:432"
  - id: F006
    severity: concern
    category: correctness
    summary: "The restore in 13.3 hardcodes `main`, which is the wrong pre-slice tree when the target is configured"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:441"
  - id: F007
    severity: concern
    category: verification
    summary: "`status` closes questions on a single `--all` listing whose completeness is tested only in the live tier, and the listing grows with history"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:200"
  - id: F008
    severity: concern
    category: scope
    summary: "The design's pending edits to 220 and 226 have no owner, and 226's breakdown would contradict this contract"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:311"
  - id: F009
    severity: concern
    category: correctness
    summary: "Task 0.2 and task 8.2 disagree on the Squadron version required for the new fixture"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:305"
  - id: F010
    severity: concern
    category: proportionality
    summary: "Fourteen commit markers and a 9-subtask §2 sit at the wrong granularity"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:134"
  - id: F011
    severity: concern
    category: correctness
    summary: "`copy_store` and `verify_copy` disagree on what the prefix is"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:83"
  - id: F012
    severity: note
    category: operator-walkthrough
    summary: "A dismissed run stays paused in Squadron with `next` null"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:219"
  - id: F013
    severity: note
    category: operator-walkthrough
    summary: "The legacy set-aside file is the only copy of answers written after the move, and it is pruned after the age limit"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:167"
  - id: F014
    severity: note
    category: design-rule
    summary: "\"Nothing grows without bound\" conflicts with unpruned question rows that grow with every pause"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:48"
  - id: F015
    severity: note
    category: sequencing
    summary: "Task 0.1's clean-tree check will fail on this planning document's uncommitted edit"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:51"
  - id: F016
    severity: note
    category: verification
    summary: "Task 0.2 has no BLOCKED line for missing 222–225 prerequisites, and the issue status is unverified here"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:38"
  - id: F017
    severity: note
    category: style
    summary: "Two commit messages exceed the length guideline"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:180"
  - id: F018
    severity: note
    category: correctness
    summary: "`mark_resume_started` has no compare-and-set, and no test asserts `not_delivered` entries in `closed_now`"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:187"
  - id: F019
    severity: pass
    category: coverage
    summary: "Every success criterion in the design maps to a task, with no scope creep"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:1"
  - id: F020
    severity: pass
    category: proportionality
    summary: "Each implementation subsection is followed by its tests, and no load test is required"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:74"
  - id: F021
    severity: pass
    category: verification
    summary: "The named schema, constants and paths exist in the repository"
    location: "src/amoeba/store/migrations.py:25"
  - id: F022
    severity: pass
    category: correctness
    summary: "The `resume_bound_seconds` formula covers every post-spawn wait in `resume.py`"
    location: "src/amoeba/operations/resume.py:123"
---

# Review: tasks — slice 228

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] An answered question whose resume was refused at the run's own pause has no exit, and member removal strands it

Scenario: `answer` writes `answered`, the resume is refused (for example, a held lock), and the run stays at the row's own pause. The row then has no exit:
- `dismiss` rejects `answered` as `not_open` (task 6.3).
- The sweep only touches rows at other pauses (task 7.4), and task 7.5 (line 268) pins that current-pause rows are never touched.
- The only remaining path is a `handle_pause` retry. The design does not promise that the retry succeeds.
- `set_up remove` does not block on `answered` rows (design line 259, tasks 10.5 and 10.6).
- A removed member is skipped as `not_in_program` before any resume (task 7.7), so after removal even the retry is gone.

Design line 259 says "D4 closes it." That holds only when the run has moved on (design lines 195–197), which is not this case. Design line 437 ("None remain") is therefore wrong.

Fix this in the design before §5, §7 and §10 are built. Decide the exit for a refused answer at the run's own pause, for example `not_delivered` once past `resume_bound_seconds`, plus a way to re-ask. Also say whether `answer` can re-send a refused answer. I did not read 223's `answer` code, so that last point is open. Tasks 7.5 and 10.6 change with the decision.

### [CONCERN] A split `XDG_STATE_HOME` between the hook and the shell silently hides the store

The state home is resolved from `XDG_STATE_HOME` in whichever process runs. If Squadron's hook environment and the PM's shell differ on that variable, the first process moves the legacy store to one home. The other process finds no legacy store, and `Store.open` creates an empty store in its own home. `status` then shows nothing, and the hook's questions are invisible, with no error. The guarantee at line 159 ("no entry point can create an empty state-home store before the move") only holds within a single home.

Likelihood is low, but the impact is high. Print the resolved store path in `status` output, and document that the hook and the CLI must resolve the same `XDG_STATE_HOME`.

### [CONCERN] The move checks the legacy file before taking the lock, so a racing process can open a store that was just deleted

Task 2.3 says steps 1–4 run only when the legacy file exists, and locks it with `mode=rw` and `BEGIN IMMEDIATE`. A process that checks existence, then waits on the lock, can open a store that the winner has just closed and deleted (step 4 deletes after close). Task 2.4's two-process test would catch this, but the task does not say how to prevent it.

Require the existence check after the lock is held. A legacy file that is already gone means the move is done. Tolerate `FileNotFoundError` on the delete. Also require the legacy connection to close on every exit, including the test exception at `LOCKED`. Otherwise the rerun in the same process waits on a lock that is still held and fails with `StoreBusyError`.

### [CONCERN] The real upgrade in §13.3 needs the PM's explicit designation under the production-database rule

§13.3 adds a key to `~/.config/amoeba/config.yaml`, runs `uv tool install --force .`, and runs `amoeba status`. That triggers the move, the migration `003` `DROP TABLE questions` rebuild on the live store, and the sweep's closures. The Production Database Protection rule in CLAUDE.md allows destructive statements only on a database the PM explicitly designated.

The design says "the install task does this" (design line 437). That assigns the step; it is not an explicit designation of the live store. Either record the PM's designation of the live store in the task file before 13.3 runs, or mark 13.3 `BLOCKED:`. The backup steps reduce data risk but do not replace the designation the rule requires.

### [CONCERN] §13.2 forbids the real-home reads that walkthrough step 2 requires, and the backup comes too late

Task 13.2 says "Never touch the real `~/.config` here." Design walkthrough step 2 (design line 389) copies the real `config.yaml` and runs `sqlite3 ~/.config/amoeba/amoeba.sqlite3 ".backup"`. An agent must either skip that step or break the task's instruction. The backup in 13.3 also runs after 13.2.

Move the backup to the start of §13. Have step 2 read from `$BACKUP`. The only real-home access is then a read-only backup, which is clearly authorized.

### [CONCERN] The restore in 13.3 hardcodes `main`, which is the wrong pre-slice tree when the target is configured

Task 0.1 reads `git.integration_branch`, and the target may be `dev/erik`. The restore reinstalls the pre-slice tool from `git worktree add … main`. For a configured target, `main` may lack 222–225, so the restored tool is the wrong one.

Use the target read in 0.1. If the target is checked out elsewhere, git refuses the worktree. The rule then says to STOP and ask the PM, not pick another branch.

### [CONCERN] `status` closes questions on a single `--all` listing whose completeness is tested only in the live tier, and the listing grows with history

Two issues with the listing `status` now uses:
- **Closure risk.** `sweep_scope` closes a waiting question as `run_gone` when its run is absent from the listing (design line 200; task 7.8). Completeness is checked only by the live test in 7.1 (task line 248), which runs only in its tier. If the live tier is not in CI, a truncated listing from a future `sq` would close every waiting question on the PM's machine, and each would have to be reopened by `answer`.
- **Time bound.** The design restates the `status` time bound as unchanged. The `--all` listing grows with every run Squadron has ever kept, not with open questions, and task 7.9 asserts only the call count.

Add a scale test with a large fixture listing and gate it in CI, or state the growth and its limit in the design.

### [CONCERN] The design's pending edits to 220 and 226 have no owner, and 226's breakdown would contradict this contract

The Pending Planning Edits (design lines 311–317) change `220-arch` and `226-slice`. The 226 edit says the MCP layer opens the store only through `open_state_store`, which this slice provides (design line 344). The task excludes these edits as "made outside this slice" and names no owner or time. 226 is already tasked with six tools, so without the edit its breakdown contradicts this contract.

Name the owner, and make the edits a planning commit before §0, or add a task that does it.

### [CONCERN] Task 0.2 and task 8.2 disagree on the Squadron version required for the new fixture

Task 0.2 (line 57) blocks on `sq` below 0.24.24, which matches D10. Task 8.2 requires the new fixture to be recorded "from `sq` 0.24.27 or later." An agent with 0.24.24–0.24.26 passes 0.2, then cannot record the fixture, and no BLOCKED line explains why.

Change 8.2 to 0.24.24, or name the version the fixture must come from and add a BLOCKED line for older versions.

### [CONCERN] Fourteen commit markers and a 9-subtask §2 sit at the wrong granularity

The markers are at lines 134, 159, 180, 199, 242, 259, 281, 295, 310, 334, 372, 406, 422 and 443. Almost every section has one, and §7 has three. The rule is markers at working, tested points, not after every task. Section 2 has nine subtasks and one commit at the end.

Keep one file; splitting it is not needed. Move the markers to layer boundaries: after §2, after §5 (merge §3–§5, the store layer, which is working and tested), after §7, after §10, after §11, and after §13. That gives six or seven commits.

### [CONCERN] `copy_store` and `verify_copy` disagree on what the prefix is

Task 2.1 defines `copy_store(old, new, path_prefixes, …)` (plural) and `verify_copy(old, new, old_prefix)` (singular). The prose describes one legacy prefix. The design (line 162) uses the same ambiguous wording.

Pick one type, a single `old_prefix: str`, for both. If the two functions disagree on the prefix, the rewrite and the verify check can test different things.

### [NOTE] A dismissed run stays paused in Squadron with `next` null

The exit is outside Amoeba (Squadron's own commands), so this is not a dead end. The `closed` line in `status` should still say the run is still paused in Squadron, or the PM will not know it is waiting.

### [NOTE] The legacy set-aside file is the only copy of answers written after the move, and it is pruned after the age limit

Recovery is manual SQLite reading, and the file is pruned after `prune_after_days`. That is acceptable for a rare case. The stderr line written at move time should say how to recover the file.

### [NOTE] "Nothing grows without bound" conflicts with unpruned question rows that grow with every pause

Line 48 says nothing Amoeba writes grows without bound. Line 130 keeps question rows unpruned and calls them bounded by pauses. Rows grow with every pause for the life of the store. That is a bound by use, not a bound. Either say the growth is linear in pauses and accepted, or give a retention rule. Task §11 repeats "store rows are not pruned" without this.

### [NOTE] Task 0.1's clean-tree check will fail on this planning document's uncommitted edit

The working tree shows the task file as modified and uncommitted. The planning commit should land before the branch is cut, or 0.1 fails on its first check.

### [NOTE] Task 0.2 has no BLOCKED line for missing 222–225 prerequisites, and the issue status is unverified here

Task 0.2 checks that 222–225 files exist (line 56) but has no BLOCKED line for a missing prerequisite, unlike its `sq` checks. The header says "Closes amoeba#34, #36, #37 (verified open 20261112)." I could not run `gh issue view` here, so the issue states and the `sq` flags are unverified in this review. Add a 0.2 step that runs `gh issue view` for 34, 36 and 37, and a BLOCKED line for missing prerequisites.

### [NOTE] Two commit messages exceed the length guideline

The commit at line 134 is 74 characters and the one at line 180 is 83. Shorten them, for example "feat: count the answer limit since the last PM answer".

### [NOTE] `mark_resume_started` has no compare-and-set, and no test asserts `not_delivered` entries in `closed_now`

The design's Patterns section (design line 321) says resume start is a compare-and-set. Task 5.1 defines `mark_resume_started` with no row check. Either give it a result or say it is unconditional. Separately, task 7.9 (lines 289–292) never asserts that `closed_now` lists `not_delivered` answers, which task 7.8 specifies.

### [PASS] Every success criterion in the design maps to a task, with no scope creep

Design criteria at lines 356–377 map to tasks: the move and single-home checks (§2, §13.3), dismiss and `closed` (§6), precedent and the limit (§4), the sweep and `closed_now` (§7), `set_up remove` (§10), prune (§11), `wrong_checkout` (§8), the calls log and `last_call` (§9), docs and doc tests (§12), and the walk test (§13.1). I found no criterion without a task and no task without a criterion. Pending Planning Edits are excluded, which is a coverage gap (see the 220/226 finding above).

### [PASS] Each implementation subsection is followed by its tests, and no load test is required

Each implementation subsection is followed by its tests (1.1→1.2, 2.1→2.2, 2.3→2.4, …, 12.1→12.2). The design restates no numeric NFR except the `status` time bound, which is covered by the finding above.

### [PASS] The named schema, constants and paths exist in the repository

`src/amoeba/store/schema/` holds only `001_baseline.sql` and `002_pause_handling.sql`, and neither has a `CREATE INDEX`, so task 3.3's "no index to recreate" is true. `EXPECTED_SCHEMA_VERSION` is 2 at `migrations.py:25`. `COUNT_AUTOMATIC_ANSWERS` and `SELECT_PM_PRECEDENT` are in `store/sql.py`. `TERMINATE_GRACE_SECONDS`, `RESUME_POLL_INTERVAL_SECONDS`, `RUN_POLL_TIMEOUT_SECONDS` and `BUSY_TIMEOUT_SECONDS` all exist. The test and doc paths I checked exist. I did not find a 224 schema-pin test by name, so task 0.2's locate step is needed.

### [PASS] The `resume_bound_seconds` formula covers every post-spawn wait in `resume.py`

The formula in task 7.2 matches the post-spawn waits: the wait loop's poll and sleep (`_follow`, lines 133–141), the poll after termination (`_after_timeout`, line 155), the SIGTERM and SIGKILL grace waits in `terminate_group` (`processes.py:110`), and the store write. `resume_started_at` must be set after the pre-spawn poll (`resume.py:93`) and just before `deps.spawn` (line 108), which task 7.2 says. The one unbounded wait is the `child.wait()` at `processes.py:115` after SIGKILL. It is not counted, and it does not need to be.

### Run Digest

- Response length: 16679 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 824545 / 605039 / 219494 / 101226 / not computed
- Duration: 457.4 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 22
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 22
- Finding-shaped matches — surviving validation: 22
