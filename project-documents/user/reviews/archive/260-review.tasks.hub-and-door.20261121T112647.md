---
docType: review
layer: project
reviewType: tasks
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/260-tasks.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: 0f6b5eace724508ccb7ce573294cdfc878cab464
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 26
effort: xhigh
turns: 27
promptTokens: 1031316
cachedTokens: 827633
cacheWriteTokens: 203669
completionTokens: 65545
durationSeconds: 281.0
costUsd: 0.396019
costBasis: provider
runId: run-20261121-p5-613fe239
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "3.4 exempts test modules that insert records, contradicting D12"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:140"
  - id: F002
    severity: concern
    category: sequencing
    summary: "3.1 calls `Store.act_as`, which 3.2 creates"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:127"
  - id: F003
    severity: concern
    category: consistency
    summary: "`OPERATIONAL_ERRORS` lives in `wiring`, which the hub may not import"
    location: "src/amoeba/wiring.py:84"
  - id: F004
    severity: concern
    category: coverage
    summary: "The load test's CI gate is implicit"
    location: ".github/workflows/ci.yml:39"
  - id: F005
    severity: concern
    category: sequencing
    summary: "16.2 says \"stop\" for the whole slice, but only 17.3 depends on it"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:415"
  - id: F006
    severity: concern
    category: consistency
    summary: "17.3 omits the `start` module that 11.2a says to record"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:431"
  - id: F007
    severity: concern
    category: scope
    summary: "13.3 and 10.1 bundle too many behaviors for one junior task"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:349"
  - id: F008
    severity: note
    category: coverage
    summary: "No test for a store that fails to open during a call (D8)"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:284"
  - id: F009
    severity: note
    category: scope
    summary: "Proportionality and commit cadence are acceptable"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md"
  - id: F010
    severity: pass
    category: coverage
    summary: "Success criteria and decisions have tasks; the file's codebase claims check out"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md"
---

# Review: tasks — slice 260

**Verdict:** FAIL (all findings resolved 20261121 in the task file)
**Model:** claude-haiku-5-5

## Findings

### [FAIL] 3.4 exempts test modules that insert records, contradicting D12

Task 3.4 keeps `Store.open` in `tests/store/test_store.py`, `test_schema.py`, `test_schema_holds_no_mirrored_state.py` and `relocate_support.py`, and says "no assertion changes." Three of those four insert records. `test_store.py` calls `Store.open` at line 62 and calls `insert_member` inside a write at line 144. `relocate_support.py` opens the store at line 33 and seeds programs, members, questions and answers at lines 34 to 66. `test_schema.py` seeds rows at lines 49 to 146. Once 3.2 binds `owner_id` from `transaction.acting()`, those inserts raise `NoActingMachineError`. D12 says tests that open a store and insert records must set the acting machine with the same helper. The exemption should cover only modules that never insert. `test_schema_holds_no_mirrored_state.py` matched none of my insert patterns, so it can stay. The other three should switch to `open_local_store`.

### [CONCERN] 3.1 calls `Store.act_as`, which 3.2 creates

`act_as_local` in 3.1 calls `store.act_as(...)`, but 3.2 introduces `Store.act_as` at line 132. There is no `def act_as` in `src` today. The 3.1 success criterion "pyright clean" cannot hold at that point. Move `Store.act_as` and `Transaction.acting()` into 3.1, or reorder the two.

### [CONCERN] `OPERATIONAL_ERRORS` lives in `wiring`, which the hub may not import

D6 and 10.1 need the hub to classify "today's operational errors" as `hub_error`. That tuple is `OPERATIONAL_ERRORS` in `wiring.py`, with five members: `AmoebaHomeError`, `ConfigError`, `ContextForgeError`, `SquadronError` and `StoreError`. D2 and the import rules forbid `hub` from importing `wiring`. Task 10.1 (line 280) says instead to use "the store and config error types, imported from their packages." That is a narrower, second list that will drift from the first. Add a step that moves the tuple to a module that both `wiring` and `hub.calls` import, with `wiring` re-exporting it. This also shrinks `wiring.py`, which is already at 325 lines.

### [CONCERN] The load test's CI gate is implicit

Task 15.6 (line 403) relies on "the bare `uv run pytest`, and so in CI." That is true today. The `Tests` step runs `uv run pytest` (ci.yml:39 to 40), and pyproject's `addopts` ignores only `tests/live`. But no task names the gate, and the load-test rule says CI gating must not be implicit. Add a sub-item under 15.6 that names the `Tests` step as the gate and records that `tests/load/test_door_load.py` is in its collection. The existing `--collect-only` check already confirms that locally. If the bounds need their own CI job, add it as a named CI task.

### [CONCERN] 16.2 says "stop" for the whole slice, but only 17.3 depends on it

If Docker is unavailable, "write `BLOCKED: docker unavailable` ... and stop" halts section 17 too. Only 17.3 needs the container output. 17.1, 17.2 and 17.4 do not depend on it. Change "stop" to "stop this task; 17.3 waits on it; 17.1, 17.2 and 17.4 continue."

### [CONCERN] 17.3 omits the `start` module that 11.2a says to record

Task 11.2a (line 299) adds `hub/start.py` and says to "record the added start module in the design under 17.3." Task 17.3 lists the walkthrough, the notes and "design text changed under the small-conflict rule." It does not list the Component Structure addition. Name it explicitly in 17.3.

### [CONCERN] 13.3 and 10.1 bundle too many behaviors for one junior task

13.3 covers `client.join` (fetch, fingerprint compare, save, `hello`, write, rollback), `change_address`, the three `leave` file steps, and `wiring_door.join` with its branches (refuse, set aside, finish a stopped join, `--address`), plus `wiring_door.leave`. It is effort 4 and spans two packages. Split it into 13.3a (`client/join.py`: `join` and `change_address`) and 13.3b (`wiring_door` join and leave ordering, with the D4 branches). Task 10.1 (line 277) has the same shape: nine ordered steps, hooks and refusal mapping in one module. Split the scope steps from the refusal and logging path. The file's own hedge about moving steps into `call_steps.py` already points that way.

### [NOTE] No test for a store that fails to open during a call (D8)

D8 says a failure outside the call scope, such as the store failing to open, goes through the same handler without the touch. Task 10.2 tests the in-scope failures (`hub_fault`, `hub_error`, skipped `act_as`) but not a case where `open_store` raises. Add one case to 10.2.

### [NOTE] Proportionality and commit cadence are acceptable

One file of about 440 lines, 17 sections and about 75 items for a slice with 19 decisions and roughly two dozen new modules. Each test group follows its implementation, no test goes beyond a criterion or decision, and no split into several files is needed. The 16 `**Commit**:` markers sit at section ends where checks pass, not after each task.

### [PASS] Success criteria and decisions have tasks; the file's codebase claims check out

Each functional criterion in the design (lines 627 to 652) maps to a named test: cross-machine `standing`, `withdraw` and `decisions` in 15.2; token refusals and door version in 15.3; lifecycle, backups and `--from-backup` in 15.4; kill and noise in 15.5; load in 15.6; join, leave and set-aside in 13.5; start refusals in 11.4; the PM's install unchanged in 7.4 and the baseline checks. Technical criteria are covered by each section's checks and 17.4. Claims in the file match the repo: 114 `Store.open` files, 16 record INSERT statements, `BUSY_TIMEOUT_SECONDS` in `store/store.py`, `read_schema_version`, `FakeSteps` in `tests/scripts/test_update_live.py`, the docker guide, and the sizes of `sql.py` (488), `wiring.py` (325) and `relocate.py` (235). The 17.2 docstring fix is needed: `scripts/update_live.py:3` still says "after a slice merges."

### Run Digest

- Response length: 8797 chars
- Response is newline-free: no
- Tool calls made: 26
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 27
- Tokens — prompt / cached / cache write / completion / reasoning: 1031316 / 827633 / 203669 / 65545 / not computed
- Duration: 281.0 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
