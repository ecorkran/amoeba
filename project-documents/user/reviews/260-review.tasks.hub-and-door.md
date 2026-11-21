---
docType: review
layer: project
reviewType: tasks
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS (reviewer stated FAIL; its one fail finding, F001, was fixed in the design and tasks 20261121; all fifteen findings were checked, see Resolution)
verdictSource: stated
sourceDocument: project-documents/user/tasks/260-tasks.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: 1be45d3a00c4eedc714216249b1a03600c267f62
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 894845
cachedTokens: 692313
cacheWriteTokens: 202520
completionTokens: 97937
durationSeconds: 425.0
costUsd: 0.469071
costBasis: provider
runId: run-20261121-p5-613fe239
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: design-rules
    summary: "An interrupted `join --set-aside-local` leaves a state no command ends"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:348"
  - id: F002
    severity: concern
    category: design-rules
    summary: "A store beside a set-aside store can only be ended by moving files"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:349"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Import cycle: `wiring_door` needs `wiring`"
    location: "src/amoeba/wiring.py:93"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Import cycle: `trust.py` raises an error defined in `call.py`"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:324"
  - id: F005
    severity: concern
    category: design-rules
    summary: "The backup directory sits outside the state directory, against the Amoeba rule"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:265"
  - id: F006
    severity: concern
    category: verification
    summary: "The container walkthrough cannot reach the hub from the host"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:420"
  - id: F007
    severity: concern
    category: sequencing
    summary: "The container commit marker sits after a task that can BLOCK"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:423"
  - id: F008
    severity: concern
    category: sizing
    summary: "Test bullets pack many behaviours into one checkbox"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:314"
  - id: F009
    severity: note
    category: verification
    summary: "Load-test CI gate is explicit and verified; no separate task is needed"
    location: ".github/workflows/ci.yml:40"
  - id: F010
    severity: note
    category: coverage
    summary: "The 261 seam criterion has no test in 260"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:663"
  - id: F011
    severity: note
    category: verification
    summary: "17.4 says \"all pass\"; 0.2 allows baseline failures"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:438"
  - id: F012
    severity: note
    category: verification
    summary: "The `uvicorn` upper bound \"below the next major\" is `<1`"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:71"
  - id: F013
    severity: note
    category: clarity
    summary: "11.2a names `open_store`; the opener is `open_hub_store` elsewhere"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:302"
  - id: F014
    severity: note
    category: design-rules
    summary: "The temp client file has no named cleanup"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:193"
  - id: F015
    severity: note
    category: conventions
    summary: "Boundary parsing is not named as Pydantic"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:241"
  - id: F016
    severity: pass
    category: coverage
    summary: "Success criteria are covered"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:625"
  - id: F017
    severity: pass
    category: verification
    summary: "Prerequisites and facts the task file names are present"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:63"
  - id: F018
    severity: pass
    category: sequencing
    summary: "Sequencing and the test-with-implementation pattern are sound"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:106"
---

# Review: tasks — slice 260

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] An interrupted `join --set-aside-local` leaves a state no command ends

Task 13.2 writes the closed mark, then checkpoints and renames. A kill between the mark and the rename leaves the store at `amoeba.sqlite3` carrying the mark, with no set-aside file and no client file (13.3b writes the client file last, line 355). From there:
- Local writes fail with a message saying the store went to the hub (4.2, line 157), though nothing is joined. The guard passes because it checks only the client file (6.3, line 199).
- `leave` (13.3b, line 355) finds no set-aside file, skips put-back, and leaves the mark in place.
- Re-running `join --set-aside-local` writes the mark "under the write lock" (13.2). If that write goes through the normal write path, it fails on the mark it is trying to write. If it bypasses the check, it succeeds. Neither the task nor D4 says which. 13.5 (line 362) tests only a stop after the rename.

The rule "every state has an exit" is not met. Fix: write the mark on a plain connection, as `put_back` does, so re-entry is idempotent. Have `leave` clear a mark on the store path when there is no client file and no set-aside store. Add a test that stops after the mark write.

### [CONCERN] A store beside a set-aside store can only be ended by moving files

13.2's refusal names both files and leaves the fix to whoever placed the extra file. The design says so itself (design line 736: "has no command that ends it"). The Amoeba rule requires an exit that needs no file edits, and "a person who has no command to act with is not an answer." The pair is reachable by restoring a state-directory backup over a joined home (D4). Fix: the design should name a command that ends the pair, such as moving the extra store aside to a dated name. That touches stored data, so it is a PM decision.

### [CONCERN] Import cycle: `wiring_door` needs `wiring`

7.4 builds `local_served_edges(layout)` in `wiring_door.py` from "the config loader and today's cf-backed readers". The loader is `load_config` (wiring.py:93). The default edges are built in `default_deps` (wiring.py:128). 13.1 makes `wiring` import `wiring_door`, so `wiring_door` importing `wiring` is a cycle that fails at import. Fix: `local_served_edges` takes the loader and readers as arguments from `wiring._dispatch`, so `wiring_door` imports neither.

### [CONCERN] Import cycle: `trust.py` raises an error defined in `call.py`

12.1 has `fetch_certificate` raise `HubUnreachableError`. The Context Summary (line 46) and 12.3 (lines 331-332) place that class in `client.call`. 12.3 also has `call` import `pinned_context` from `trust`, which makes `trust` → `call` → `trust`. Fix: put the four client errors in `client/errors.py`, imported by both, and say so in 12.1 and 12.3.

### [CONCERN] The backup directory sits outside the state directory, against the Amoeba rule

9.1 puts timed and pre-migration backups under a required `backup_dir`, which is outside `~/.local/state/<app>`. The Amoeba rule says databases live in the state directory. The design justifies the departure (D1 at design line 148; departures table at line 576). That conflict is the PM's to accept or reject. The task file cites only the design's departure, so record the PM's decision before 8.1 and 9.1 are checked.

### [CONCERN] The container walkthrough cannot reach the hub from the host

8.1 makes the example's `address` a placeholder host. 16.2 starts the container and runs `amoeba join <line>` from a host home, but never says what `address` the copied `hub.yaml` must carry. The join would fail with `HubUnreachableError`. Fix: 16.2 should say to set `address` to a host that reaches the published port, reading that port from `docker/compose.example.yaml`.

### [CONCERN] The container commit marker sits after a task that can BLOCK

16.2 may write `BLOCKED: docker unavailable`. The marker for section 16 comes after it. If Docker is missing, the Dockerfile and compose files from 16.1 stay uncommitted, and 17's commit sweeps them in. Fix: move the marker to after 16.1 and let 16.2's note travel with 17.

### [CONCERN] Test bullets pack many behaviours into one checkbox

11.4's `test_start` bullet lists about ten refusal cases. 13.5 (line 362 and the join bullet above it) lists about fourteen join and leave scenarios. 10.2 (lines 287-289) is similar. A junior can tick the item with one case missing, and task-checker cannot see which. Fix: one sub-checkbox per case. The scope does not change.

### [NOTE] Load-test CI gate is explicit and verified; no separate task is needed

The `check` job runs `uv run pytest` (ci.yml:13, 39-40), and `pyproject.toml` ignores only `tests/live`. So `tests/load/test_door_load.py` is gated by the existing step, and 15.6 names it. The rule asks for a CI wiring task. This is met in substance, but 15.6's `--collect-only` check proves collection, not a CI run. A green CI run on the branch is the real proof.

### [NOTE] The 261 seam criterion has no test in 260

"261 can serve a new operation by adding to the served list and `run_served`" cannot be proven until 261 exists. The seam is covered only indirectly by 7.6 and 10.2. The 17.4 mapping note should say so, so the criterion is not later marked as a missing test.

### [NOTE] 17.4 says "all pass"; 0.2 allows baseline failures

Fix: "all pass, or only the baseline failures listed in 0.2".

### [NOTE] The `uvicorn` upper bound "below the next major" is `<1`

For a 0.x package, `<1` admits minor-version changes that D14's stall reasoning depends on. Use `<0.55` or the existing pin style. The locked version is 0.54.0 (uv.lock:849), so 0.1's recheck does not trigger.

### [NOTE] 11.2a names `open_store`; the opener is `open_hub_store` elsewhere

6.3 and 14.2 name it `open_hub_store`. Use that name in 11.2a, or a junior may create a second opener.

### [NOTE] The temp client file has no named cleanup

6.2 writes a temporary file in the config directory and renames it. A crash leaves it behind, and nothing says it is bounded. Use one fixed temp name, which bounds it to one file, and say so.

### [NOTE] Boundary parsing is not named as Pydantic

The Python rules require Pydantic at external boundaries. `load_hub_config` (8.1), `load_client_file` (6.2), `parse_join_line` (1.3) and `parse_reply` (1.2) all read external input. Name Pydantic models with `extra="forbid"`. A model's `ValidationError` also gives the one-pass error report that 8.1 asks for.

### [PASS] Success criteria are covered

Traced: FR 1–4 to 15.2. FR 5 to 12.2, 12.4 and 13.5. FR 6 to 6.4 and 13.5. FR 7 to 15.3. FR 8 to 10.2, 12.4 and 15.5. FR 9 to 10.2. FR 10 to 12.4. FR 11 and 12 to 7.4 and 14.4. FR 13 to 12.4, 14.4 and 15.3. FR 14 to 15.4. FR 15 to 5.3, 10.2 and 15.3. FR 16 and 17 to 11.4. FR 18 to 15.5. FR 19 and 20 to 9.2, 11.4 and 15.4. FR 21 to 13.5. FR 22 to 3.5, 10.2 and 15.4. FR 23 to 17.2. Technical: import rules in 1.4, 6.2 and 8.4; load test in 15.6; contract docs in 17.1. I found no deferral and no task that traces to nothing.

### [PASS] Prerequisites and facts the task file names are present

Checked: `OPERATIONAL_ERRORS` holds the five named members (src/amoeba/wiring.py:84-90). `read_schema_version` exists (src/amoeba/store/migrations.py:80), and `restore` exists in the release script (scripts/update_live.py:195). The 16 record INSERT statements match 3.2's list across the six named files. `standing` takes a `CfRun` (src/amoeba/operations/standing.py:34) and `decisions` takes `Deps` (src/amoeba/operations/decisions.py:74), so 7.1 and 7.2 match the code. The locked versions are in uv.lock: cryptography 50.0.2, starlette 1.10.0, uvicorn 0.54.0. The test helpers, docs and `tests/load` directory exist.

### [PASS] Sequencing and the test-with-implementation pattern are sound

Each test block follows its implementation. I found no dependency on a later task beyond the two import cycles above. Sections 2 and 3 commit together, as the note at line 106 says. The other commit markers sit at tested points, except the section 16 marker above.

### Run Digest

- Response length: 11260 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 894845 / 692313 / 202520 / 97937 / not computed
- Duration: 425.0 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18

## Resolution

Checked 20261121 against the task file, the design and the source. Fixed in the design (`260-slice.hub-and-door.md`, D4 and the walkthrough) and the task file.

- **F001 (fail), fixed.** Valid: the mark is committed before the rename, and a re-run `join` would fail its own mark write through the normal write path. `set_aside` now writes the mark on a plain connection holding `BEGIN IMMEDIATE`, replacing any mark, so a re-run goes on. `leave` clears a mark on the store path when no set-aside store exists. `LocalStoreClosedError` names both ways out when there is no client file. 13.5 tests a stop after the mark write.
- **F002, dropped.** The pair comes only from files placed by hand, which Amoeba's commands never make, and the refusal names both files. A command for a state only a hand edit creates adds mechanism for a case that should not occur.
- **F003, fixed.** `local_served_edges` takes the loader, readers and clock from `wiring` (7.4).
- **F004, fixed.** The four client errors move to `client/errors.py`, imported by `trust` and `call` alike.
- **F005, dropped.** The architecture requires backups that can sit on another disk from the store they protect, and the design records the departure with that reason. Backups stay out of the config directory, which is what the rule protects.
- **F006, fixed.** 16.2 sets `address` to the host and the published port.
- **F007, fixed.** The section 16 commit marker follows 16.1; 16.2's note commits with section 17.
- **F008, dropped.** Sizing only; each bullet is one test file's cases and the scope is clear.
- **F009, no action.** The reviewer agrees the CI gate is met.
- **F010, fixed.** 17.4's mapping note says how the 261 seam criterion is proven.
- **F011, fixed.** 17.4 allows the baseline failures from 0.2.
- **F012, fixed.** 0.3 says a `0.x` package is bounded below the next minor.
- **F013, fixed.** 11.2a names `open_hub_store`.
- **F014, fixed.** The client file uses the fixed temp name `client.yaml.tmp`, so a crash leaves at most one file.
- **F015, fixed.** `ClientFile`, `HubConfig` and the reply shapes are Pydantic models with `extra="forbid"`.
