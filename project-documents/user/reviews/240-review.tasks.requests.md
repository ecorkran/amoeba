---
docType: review
layer: project
reviewType: tasks
slice: requests
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/240-tasks.requests.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 4f0b2139691e9b1fbd75ed02d8264c8d4eb77ae7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
effort: xhigh
turns: 22
promptTokens: 1235290
cachedTokens: 1044374
cacheWriteTokens: 190898
completionTokens: 69113
durationSeconds: 306.8
costUsd: 0.400469
costBasis: provider
runId: run-20261115-tasks-plan-16a0f352
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks"
    location: "project-documents/user/tasks/240-tasks.requests.md:49"
  - id: F002
    severity: pass
    category: accuracy
    summary: "Referenced code and paths exist"
    location: "src/amoeba/store/sql.py:98"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Sequencing has no cycles and follows test-with"
    location: "project-documents/user/tasks/240-tasks.requests.md:56"
  - id: F004
    severity: fail
    category: no-deferral
    summary: "Timing criterion for slice 242 is deferred, not built"
    location: "project-documents/user/tasks/240-tasks.requests.md:234"
  - id: F005
    severity: fail
    category: test-coverage
    summary: "No load test for the concurrent message paths"
    location: "project-documents/user/tasks/240-tasks.requests.md:163-165"
  - id: F006
    severity: concern
    category: test-quality
    summary: "The timing test checks declared lookup counts, not calls made"
    location: "project-documents/user/tasks/240-tasks.requests.md:234"
  - id: F007
    severity: concern
    category: safety
    summary: "The live tier does not require an isolated AMOEBA_HOME"
    location: "project-documents/user/tasks/240-tasks.requests.md:271"
  - id: F008
    severity: concern
    category: safety
    summary: "\"Stop any running amoeba process\" has no procedure and may hit the PM's sessions"
    location: "project-documents/user/tasks/240-tasks.requests.md:281"
  - id: F009
    severity: concern
    category: scope
    summary: "Note pruning is built in 240, but the design says 243 owns it"
    location: "project-documents/user/tasks/240-tasks.requests.md:90"
  - id: F010
    severity: concern
    category: proportionality
    summary: "Task 4.1 and task 6.1 exceed the size limits"
    location: "project-documents/user/tasks/240-tasks.requests.md:124"
  - id: F011
    severity: concern
    category: test-coverage
    summary: "\"list -j equals the status document\" has no assertion"
    location: "project-documents/user/tasks/240-tasks.requests.md:204"
  - id: F012
    severity: concern
    category: sequencing
    summary: "Commit markers sit on every top-level section"
    location: "project-documents/user/tasks/240-tasks.requests.md:68-291"
  - id: F013
    severity: note
    category: sequencing
    summary: "Commit at 3.4 is typed `refactor` but changes behavior"
    location: "project-documents/user/tasks/240-tasks.requests.md:118"
  - id: F014
    severity: note
    category: proportionality
    summary: "Two tests go beyond the criteria"
    location: "project-documents/user/tasks/240-tasks.requests.md:247"
  - id: F015
    severity: note
    category: clarity
    summary: "Code paths are package-relative, and the task never says so"
    location: "project-documents/user/tasks/240-tasks.requests.md:51"
  - id: F016
    severity: note
    category: consistency
    summary: "The task file lists 229 as a dependency; the design does not"
    location: "project-documents/user/tasks/240-tasks.requests.md:8"
  - id: F017
    severity: note
    category: sequencing
    summary: "Task 0.1's clean-tree check fails while this file is uncommitted"
    location: "project-documents/user/tasks/240-tasks.requests.md"
  - id: F018
    severity: note
    category: schema
    summary: "No index on `deliveries.message_id`"
    location: "project-documents/user/slices/240-slice.requests.md:122"
---

# Review: tasks — slice 240

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria map to tasks

Each functional, technical and integration criterion has a task and a test. Scenario D is in 12.1, 12.2 and 14.1. Every state exit is in 12.2, with the cancel and member-removal paths in 8.2 and 10.6. The two-process accept race is in 7.3. The cursor and two-worktree case is in 9.2. Chain depth and recorded rejections are in 6.2, 7.2 and 8.2. Over-limit text is in 6.2. Sweep and retention are in 2.6. The held store is in 10.2 and 10.4. The config keys are in 3.1. The pinning, contract-docs and import-boundary checks are in 1.2, 13.1 and 15.2. The one gap is the timing criterion (below) and the `list -j` equality check (line 204).

### [PASS] Referenced code and paths exist

Verified: `ACTIVE_MEMBER`, `apply_removal` (`operations/set_up_remove.py:139`), `_anchor` (`operations/rm.py:126`), `_full_hash` and `_Version` (`operations/report_release_models.py:49,93`), `QUOTED_DATA_NOTICE` with its three test consumers, `CF_GET_TIMEOUT_SECONDS` (30.0), `MCP_CALL_DEADLINE_SECONDS` (180.0), `ANSWER_STORE_WAITS` (3), `EXPECTED_SCHEMA_VERSION` (5), and migrations 001 to 005. Modules the tasks create (`member_reference.py`, `release_fields.py`, `quoted_data.py`) are absent as expected.

### [PASS] Sequencing has no cycles and follows test-with

Every implementation task has its test task directly after it. Dependencies run store, then config and moves, then models, resolution, operations, status and rendering, doors, end-to-end and docs, live tier, then live store. I found no cycle.

### [FAIL] Timing criterion for slice 242 is deferred, not built

Design line 291 requires the 240 timing test to add 242's `START_BOUND_SECONDS` to `send`, `reply` and `cancel`. Task 11.5 says "Slice 242 adds its term … this test names no 242 symbol", so 240 ships without it. The Amoeba Design Rules reject any breakdown that defers in-scope behavior to a later slice. The design fixes the value at 30 s, so 240 can define it now and 242 can consume it. The test should then assert 105 s + 30 s = 135 s for `send` and 75 s + 30 s = 105 s for `reply` and `cancel`, all under 180 s.

### [FAIL] No load test for the concurrent message paths

The Python rules require at least one `tests/load/` test for any concurrency path, asserting latency, throughput or resource bounds. Slice 240 adds one: the first-accept-wins write race in `reply`. Task 7.3 checks correctness under `tests/operations/` and does not bound latency. The repo already has the precedent `tests/load/test_no_cf_under_write_lock.py`, which checks that `report_release` never calls `cf` under the write lock. The design repeats that invariant for `send`, `reply`, `cancel` and `inbox` (design line 97). Add a task that extends the probe to the four message operations and runs concurrent accepts against a realistic store with a latency bound. No CI task is needed: `.github/workflows/ci.yml:40` runs bare `uv run pytest`, and `pyproject.toml:64` excludes only `tests/live`. The task should say that the new file is gated by that existing run.

### [CONCERN] The timing test checks declared lookup counts, not calls made

Task 11.5 computes each worst case from the lookup counts in `wiring_messages.py`, and the test reads those same constants. If someone adds a fourth `cf` lookup to `send`, the constant and the bound move together and the test still passes. Run each operation's worst path against the stub `cf`, assert the recorded call count is at most the declared count, and compute the bound from the recorded count.

### [CONCERN] The live tier does not require an isolated AMOEBA_HOME

Task 14.1 runs real `send`, `reply`, `cancel` and `rm`, and the `rm` cascade writes to the store. The design's walkthrough (design line 303) says these steps "use a throwaway home so the live store is untouched", but 14.1 does not say so. The existing live tiers isolate this way (`tests/live/program/consumer.py` builds "one AMOEBA_HOME and config"). Require the same, and have the tier assert that the live store path is never opened.

### [CONCERN] "Stop any running amoeba process" has no procedure and may hit the PM's sessions

The step says to stop any running `amoeba` or `amoeba-mcp` process, then gives only a check that finds none. The CLAUDE.md designation covers migrations and their config edits, not killing processes, and a running `amoeba-mcp` may be the PM's live session. Replace it with: check, and if anything is running, write `BLOCKED:` under this task and stop.

### [CONCERN] Note pruning is built in 240, but the design says 243 owns it

D1 (design line 126) says "243 adds the note writer and its retention". D6 (design line 174) has the 240 sweep prune notes, and tasks 2.5 and 2.6 build that, tested only with hand-inserted rows, since 240 never writes a note. The two design decisions contradict each other. Pick one. The task follows D6, which fits the no-deferral rule, but it builds code no real path reaches.

### [CONCERN] Task 4.1 and task 6.1 exceed the size limits

Task 4.1 puts four request models, four results, two views, three outcome enums, the limit constants and the reply validators into one `message_models.py`, with no split instruction. The project limit is about 300 lines per file. Task 6.1 describes the whole send flow as one step, which would be one long function against the about-50-line limit. Split 4.1 into `message_models.py` and a views module, and state in 6.1 that the flow is separate helpers.

### [CONCERN] "list -j equals the status document" has no assertion

Design line 286 requires `list -j` to equal the `status` document for the new request fields. Task 10.4 checks only a key snapshot. Add an equality assertion on a fixture that has requests in it.

### [CONCERN] Commit markers sit on every top-level section

There are 16 markers for 15 sections. That is the default of one commit per top-level task, so the markers do not pick out working points. Group the commits by working point: schema and store (1 and 2), config and moves (3), the operations (4 to 9, in two or three commits), status, list and wiring (10 and 11), and tests and docs (12 to 15). Each boundary must still pass checks.

### [NOTE] Commit at 3.4 is typed `refactor` but changes behavior

Task 3.1 makes two config keys required, so an old config now fails. That is a behavior change. Type the commit `feat:`, or split the config commit from the moves, which stay `refactor:`.

### [NOTE] Two tests go beyond the criteria

Task 12.3 (retention end to end) repeats 2.6 and 10.2. Drop it or fold it into 12.2. The "ten runs in a row" check in 7.3 (line 165) is a flakiness step, not a criterion.

### [NOTE] Code paths are package-relative, and the task never says so

Paths such as `store/schema/` sit under `src/amoeba/` (verified: `src/amoeba/store/schema/001_baseline.sql` through `005`). Tests and `docs/` sit at the repo root. Add one line to the Context Summary that states both roots.

### [NOTE] The task file lists 229 as a dependency; the design does not

Slice 229 is `status: complete`, so this is not a blocker. The design's frontmatter lists only 220, but its CLI contract (text by default, `-j`) comes from 229. Add 229 to the design's dependencies.

### [NOTE] Task 0.1's clean-tree check fails while this file is uncommitted

At session start, git status showed this file modified and uncommitted. Task 0.1 requires a clean tree on the target, so commit the planning document once its review loop finishes, before Phase 6 starts.

### [NOTE] No index on `deliveries.message_id`

Pruning and the removal cascade delete deliveries by `message_id`, and SQLite does not index a foreign key automatically. The design says a wrong column costs a later migration. Adding `(message_id)` to D1 costs nothing now. This belongs to the design's author.

### Run Digest

- Response length: 11965 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 1235290 / 1044374 / 190898 / 69113 / not computed
- Duration: 306.8 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
