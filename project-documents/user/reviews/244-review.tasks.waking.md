---
docType: review
layer: project
reviewType: tasks
slice: waking
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/244-tasks.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 504c8cc9beec9c79039e5f4b2b1f8d3f72073cef
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
effort: xhigh
turns: 26
promptTokens: 1310139
cachedTokens: 1118858
cacheWriteTokens: 191263
completionTokens: 78196
durationSeconds: 349.7
costUsd: 0.429957
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: spec-consistency
    summary: "An overdue wake row is \"running\" in the tasks but \"not running\" in the success criteria"
    location: "project-documents/user/tasks/244-tasks.waking.md:199"
  - id: F002
    severity: concern
    category: coverage
    summary: "The \"two sends at once\" guarantee has no test, and the load-test rule is not addressed"
    location: "project-documents/user/tasks/244-tasks.waking.md:170"
  - id: F003
    severity: concern
    category: size
    summary: "Task 3.1 bundles too many functions into one task"
    location: "project-documents/user/tasks/244-tasks.waking.md:98"
  - id: F004
    severity: concern
    category: size
    summary: "Task 5.1 is too large for one file and one task, and the boundary handler needs a lint decision"
    location: "project-documents/user/tasks/244-tasks.waking.md:136"
  - id: F005
    severity: concern
    category: size
    summary: "Task 6.4 holds about 14 cases plus three other groups in one bullet"
    location: "project-documents/user/tasks/244-tasks.waking.md:171"
  - id: F006
    severity: concern
    category: process
    summary: "Task 0.1 commits design amendments to the target during Phase 6"
    location: "project-documents/user/tasks/244-tasks.waking.md:59"
  - id: F007
    severity: concern
    category: clarity
    summary: "Task 8.2's harness wording is ambiguous and conflicts with D8"
    location: "project-documents/user/tasks/244-tasks.waking.md:218"
  - id: F008
    severity: concern
    category: proportionality
    summary: "The plan is overweight for an effort-3 slice"
    location: "project-documents/user/tasks/244-tasks.waking.md"
  - id: F009
    severity: concern
    category: error-handling
    summary: "P7.3's restore uses a commit that may be missing, with no stop condition"
    location: "project-documents/user/tasks/244-tasks.waking.md:270"
  - id: F010
    severity: note
    category: docs-accuracy
    summary: "The design says the plan's entry 5 reads \"240, 241\", but the plan already reads \"240, 241, 242, 243\""
    location: "project-documents/user/slices/244-slice.waking.md:244"
  - id: F011
    severity: note
    category: docs-accuracy
    summary: "9.2 misses one architecture sentence and edits a document the design does not list"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md:188"
  - id: F012
    severity: note
    category: design-rule
    summary: "The orphaned command's exit depends on convention, not enforcement"
    location: "project-documents/user/slices/244-slice.waking.md:193"
  - id: F013
    severity: note
    category: sequencing
    summary: "The fixture agent is built before the docs, which departs from the design's order"
    location: "project-documents/user/tasks/244-tasks.waking.md:211"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every success criterion maps to a task"
    location: "project-documents/user/tasks/244-tasks.waking.md"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit markers are sound"
    location: "project-documents/user/tasks/244-tasks.waking.md"
  - id: F016
    severity: pass
    category: docs-accuracy
    summary: "Facts the tasks depend on were checked against the repo"
    location: "project-documents/user/tasks/244-tasks.waking.md"
---

# Review: tasks — slice 244

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] An overdue wake row is "running" in the tasks but "not running" in the success criteria

The design contradicts itself. The success criterion (`244-slice.waking.md:281`) and State Management (`:108`) say an unended row "stops reading as running" at `deadline_at`. D9 (`:213`) defines `running` as the unended row "live or past its deadline". Tasks 3.1 (line 103) and 7.1 (line 195) follow D9, and 7.2 (line 199) asserts a past-deadline row is still `running`. An implementer cannot satisfy both. Settle the wording in the design, then align 3.1, 7.1, 7.2 and the renderer's overdue line.

### [CONCERN] The "two sends at once" guarantee has no test, and the load-test rule is not addressed

D2 (`244-slice.waking.md:139`) relies on the lock: two concurrent sends must produce one claimed row and one spawn. No task tests this. The project's Python rules (`.claude/rules/python.md`, load-test tier) require a `tests/load/` test for concurrency paths, with CI gating. The wake claim, the detached spawn and the wrapper's timeout are such paths. Add a `tests/load/` task: N concurrent sends to one member with a command yield exactly one `wakes` row and one spawn, with a latency bound. Add the CI gate if the repo gates load tests (not verified here).

### [CONCERN] Task 3.1 bundles too many functions into one task

3.1 covers the five-check `claim_wake`, `can_wake`, `LIVE_WAKE`, `get_wake`, `set_command_pid`, `finish_wake`, `wake_summary`, `prune_wakes` and `wakes_due`, across `store/wakes.py` and `store/sql_wakes.py`. Split it into a claim task (`claim_wake`, `can_wake`, `LIVE_WAKE`, with the claim tests from 3.2) and a finish-and-reads task (`finish_wake`, `set_command_pid`, `get_wake`, `wake_summary`, `prune_wakes`, `wakes_due`, with their tests).

### [CONCERN] Task 5.1 is too large for one file and one task, and the boundary handler needs a lint decision

5.1 covers pre-start failures, the timed wait, the finish write, and the process-boundary handler, in a file the task itself caps at about 300 lines. Split it into pre-start and environment (`build_wake_environment`, the `start_failed` rows) and run-and-finish (the wait, `terminate_group`, the boundary handler). The task also needs to say how the one `except Exception` passes `ruff check`. Check whether BLE001 flags it; if so, it needs an explicit `# noqa: BLE001` with the reason.

### [CONCERN] Task 6.4 holds about 14 cases plus three other groups in one bullet

6.4 mixes spawn, limit, no-command, failure-to-start, TTL and expiry cases with retry rules, store-open counts, the write-lock check, the `StoreError` path and the message-text check. Split it into 6.4 (spawn, limit, start-failure cases) and a new 6.5 (store opens, pre-check and lock, retry rules, message text). Renumber the timing test to 6.6.

### [CONCERN] Task 0.1 commits design amendments to the target during Phase 6

The repo's Git Rules say Phase 6 work "ends with the work committed on the slice branch." 0.1 commits the design amendment to the target before 0.2 creates the branch. Either make 0.2 create the branch first and let the amendment be the branch's first commit, or move the amendment to before Phase 6. The branch will still carry the same design text when merged.

### [CONCERN] Task 8.2's harness wording is ambiguous and conflicts with D8

"Each CLI call that sends gets `AMOEBA_HOME` a throwaway directory" read literally gives every call its own empty store, so the send-then-list-then-wake assertions cannot see each other. It should say one throwaway home per test, shared by that test's calls. "Config values ... added to the example config" could mean editing `docs/config-contract.md`, which D8 forbids (the suggested values appear once, in that example). It should say the test's config is the example text with the two values overridden in the test.

### [CONCERN] The plan is overweight for an effort-3 slice

The file has 37 tasks (33 numbered plus four in Phase 7) and 13 commit markers for a slice the plan rates effort 3. Suggested merges: 0.1 with 0.2; 1.1 with 1.2; 7.3 with 7.4; 5.3 with 5.4. Task 10.1 (a rehearsal on a copy) is not in the design. It is cheap and defensible, but it is a candidate for cutting if the PM wants the plan trimmed. The design itself is large, so some of this weight is inherited.

### [CONCERN] P7.3's restore uses a commit that may be missing, with no stop condition

The restore reinstalls "the target commit recorded in 10.2". If that note is empty, the step has no commit and no instruction. Add: "If no commit hash is recorded under 10.2, stop with an error." Reinstalling the wrong code during a failed live migration is the costliest mistake in this file.

### [NOTE] The design says the plan's entry 5 reads "240, 241", but the plan already reads "240, 241, 242, 243"

The plan (`240-slices.agent-messaging.md:105`) already lists all four dependencies. The Departures bullet is stale, and 9.2's Dependencies edit is a no-op. Correct the design line, and let 9.2 check before editing.

### [NOTE] 9.2 misses one architecture sentence and edits a document the design does not list

The "Store and config" paragraph says the new settings have "defaults defined once in the config layer". D8 says they are required with no default in code. 9.2 should name this sentence for amendment, since the design's Departures mention only the columns and keys. Also, 9.2 amends `240-slice.requests.md`, which the design's amendment list does not name. Keep it only if the PM wants 240's design updated.

### [NOTE] The orphaned command's exit depends on convention, not enforcement

For a command whose wrapper was SIGKILLed, the exit is the command's own cap or a manual kill of the pid `list` shows. The docs test (9.1) checks only the example's cap, not any real command's. This meets the "every state has an exit" rule only by convention, and the design says so. Acceptable as written; the PM should know it.

### [NOTE] The fixture agent is built before the docs, which departs from the design's order

Design Development Approach step 6 puts the docs before the fixture agent. The task file reverses them. The reversal is correct, because 9.1's example uses the fixture's `--max-seconds` flag, but the file should say why.

### [PASS] Every success criterion maps to a task

Functional: wake once and no second wake while running (6.4, 8.2); live and unconfirmed sessions and same-id retries (3.2, 6.4, 8.2); timeout, group kill and grandchild SIGTERM (5.2); SIGKILL orphan and sweep (8.2, 6.7); wrapper failures (5.2); limit and the 24-hour exit (3.2, 6.4, 7.2); start failures (5.2, 6.4); no-second-open and pre-check lock (6.2, 6.4); exit codes and `wake_problem` (5.2, 6.4, 7.2); no message text (6.4, 8.2); exact environment (5.2); example cap (9.1); add flags and MCP schema (4.2, 4.4). Technical: cleanup and log prune (6.6, 6.7); config and pinned checks (1.2, 2.2, 9.1, 10.2); timing bound (6.5); checks (0.2, 10.2). Integration: unchanged 240–243 tests (10.2); live migration (P7.1–P7.4).

### [PASS] Sequencing, test-with pattern and commit markers are sound

Each implementation task is followed by its tests. The order runs config, migration, store, CLI add, wrapper, send step, status, fixture, docs, verification, then Phase 7, with no cycles. The 13 markers fall at working points. Only 0.1's marker (flagged above) lands off-branch.

### [PASS] Facts the tasks depend on were checked against the repo

Confirmed: schema files 001–005 exist, and 240–242 are not yet built, as 0.1 expects. `ACTIVE_MEMBER` is `removed_at IS NULL`, so `rm` is a soft delete and the `wakes` foreign key is safe. `BUSY_TIMEOUT_SECONDS` is 5.0 and `MCP_CALL_DEADLINE_SECONDS` is 180, so the 160 s figure fits. `start_child` and `terminate_group` match D5 and D6. `config_home()` honours `AMOEBA_HOME`, so 10.1's copy of the config into the throwaway home is correct. The `(244) Waking` anchor in 9.2's `sed` exists (plan line 95). 243's task 9.2 already changes the Implementation Order line, and 244's conditional check handles it.

### Run Digest

- Response length: 10018 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 26
- Tokens — prompt / cached / cache write / completion / reasoning: 1310139 / 1118858 / 191263 / 78196 / not computed
- Duration: 349.7 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
