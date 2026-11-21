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
reviewedSha: abca38c7763ff5615335ad6eab6be1d5d7db5d42
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
effort: xhigh
turns: 20
promptTokens: 976024
cachedTokens: 745199
cacheWriteTokens: 230813
completionTokens: 81990
durationSeconds: 357.9
costUsd: 0.460221
costBasis: provider
runId: run-20261121-p5-613fe239
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: coverage
    summary: "The \"261 can serve a new operation\" criterion is proven only by 261's own tests"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:474"
  - id: F002
    severity: fail
    category: sequencing
    summary: "Raw test inserts into the record tables will abort under the owner triggers and sit outside 3.2 and 3.4"
    location: "tests/store/message_support.py:75"
  - id: F003
    severity: fail
    category: rules
    summary: "A local store beside a set-aside store has no command exit"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:229"
  - id: F004
    severity: concern
    category: sequencing
    summary: "The table-count pin in test_contract_docs.py breaks at 2.1"
    location: "tests/test_contract_docs.py:101"
  - id: F005
    severity: concern
    category: consistency
    summary: "Step 1.2's success line contradicts its own step"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:90"
  - id: F006
    severity: concern
    category: consistency
    summary: "17.3 omits client/errors.py, which the Context Summary says to record"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:470"
  - id: F007
    severity: concern
    category: coverage
    summary: "JoinError and NotServedError have no step that joins OPERATIONAL_ERRORS"
    location: "src/amoeba/wiring.py:84"
  - id: F008
    severity: concern
    category: rules
    summary: "An example value sits beside the lock-version retrieval"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:71"
  - id: F009
    severity: concern
    category: rules
    summary: "Backups sit outside the state directory, against a rule that names no exception"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:148"
  - id: F010
    severity: note
    category: consistency
    summary: "hub.yaml load errors are typed two ways"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:314"
  - id: F011
    severity: note
    category: verification
    summary: "The load test's CI gate is the existing Tests step"
    location: ".github/workflows/ci.yml:39"
  - id: F012
    severity: note
    category: completeness
    summary: "Certificate failure and connection failure are not distinguished"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:351"
  - id: F013
    severity: note
    category: sizing
    summary: "The task file is large but does not need a split"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md"
  - id: F014
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks, apart from the 261 item"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:627"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence hold"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:106"
---

# Review: tasks — slice 260

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The "261 can serve a new operation" criterion is proven only by 261's own tests

The design's Integration Requirement (line 665) must be proven in this slice. Task 17.4 says it is "proven by 7.6 and 10.2 here and by 261's own tests." Neither 7.6 nor 10.2 adds a seventh name. Both exercise only the six existing operations, so nothing here shows that adding a name to `SERVED_OPERATIONS` and a `run_served` case works with no change to the call format. The Amoeba no-deferral rule makes this a rejection. Fix: add a test in 7.6 or 10.2 that patches a stub name into the served set and the dispatch that `run_served` uses, sends it through `handle_call`, and asserts the result with the door version unchanged. Remove "and by 261's own tests" from 17.4.

### [FAIL] Raw test inserts into the record tables will abort under the owner triggers and sit outside 3.2 and 3.4

D12's triggers abort any insert whose `owner_id` is null, whether or not an acting machine is set. Task 3.2 greps only `src/amoeba` (line 133). Task 3.4 (line 140) replaces only `Store.open(` calls. A grep of `tests/` finds raw SQL inserts into record tables that neither step reaches:

- `tests/store/message_support.py:75` (messages, a shared helper)
- `tests/mcp_server/test_inbox_watcher.py:205` and `:270` (messages, inside `Store.open` plus `store.write()`, which 3.4 converts but which still omits `owner_id`)
- `tests/operations/test_pause_held.py:210` (messages)
- `tests/store/test_member_removal.py:171` (releases)
- `tests/store/test_settled.py:84` (answers)
- `tests/live/waking/test_waking_live.py:193` (sessions, via `sqlite3.connect`; the default `addopts` skip `tests/live`, so this surfaces only on an explicit live run)

`tests/store/test_migrations.py` and `tests/operations/test_state_move_directories.py` also insert raw rows, but at older schema versions. The implementer must confirm each one runs before migration 011.

So 3.4's success ("full suite back to the baseline") cannot be met as written. Line 55 says "If any other existing test fails, fix the new code, not the test." An implementer following that would weaken the triggers instead of fixing the inserts. Fix: 3.4 should also grep `tests/`, including `tests/live`, for `INSERT INTO` into the twelve tables and bind `owner_id` (and `machine_id` for sessions) in each raw insert. Line 55 should carve out this case: the test's insert changes, the trigger does not.

### [FAIL] A local store beside a set-aside store has no command exit

The Amoeba rule "every state has an exit" requires each state to end with nobody editing files. D4 says this pair "comes only from files placed by hand" and that the refusal "names both files, so whoever placed the extra file can move it away." That is an exit by hand. The walkthrough lists it as resolved by the refusal (line 739), which does not meet the rule. Tasks 13.2 (lines 366–368) and 13.3b (line 374) implement only the refusal. Fix: the design must name a command that resolves the pair without deleting data. One option is for `leave` to rename the extra file to a timestamped name in the state directory and then put the set-aside store back. Add a task and a test for it.

### [CONCERN] The table-count pin in test_contract_docs.py breaks at 2.1

`test_the_store_contract_names_every_table_and_column` asserts `len(schema) == 14`. Migration 011 adds four tables (`owners`, `machines`, `call_results`, `closed_mark`), so the count becomes 18 when 2.1 lands. Task 2.1 (line 115) says to change "only the version number" in failing tests, which does not cover this count. Fix: name this pin in 2.1 and give its new value, 18.

### [CONCERN] Step 1.2's success line contradicts its own step

Step 1.2 (line 87) requires `parse_reply` to validate against two Pydantic models, but the success line says "imports only the standard library." An implementer will either fail the check or skip the Pydantic step. Fix: change the success line to "imports only the standard library and pydantic." `pydantic` 2.13.5 is in `uv.lock`.

### [CONCERN] 17.3 omits client/errors.py, which the Context Summary says to record

The Context Summary (line 46) says "Record the added `client/errors.py` in the design under 17.3." Task 17.3 (line 470) lists `hub/start.py`, `hub/call_refusals.py` and `operations/errors.py`, but not `client/errors.py`. Fix: add it.

### [CONCERN] JoinError and NotServedError have no step that joins OPERATIONAL_ERRORS

The Context Summary (line 44) says each named error joins `OPERATIONAL_ERRORS` when it is created. Only 6.2 (`ClientFileError`) and 12.3 (the three client errors) say so in a task. `JoinError` (created in 1.3, line 93) and `NotServedError` (13.1, line 363) have no such step. The CLI boundary catches only the tuple (`src/amoeba/cli/main.py:64`), so without the step a bad join line or a `NotServedError` on a joined machine would escape as a traceback instead of exiting 3 with one line. Fix: add the tuple join to 1.3 and to 13.1.

### [CONCERN] An example value sits beside the lock-version retrieval

Step 0.1 (line 64) says to read the uvicorn version from `uv.lock`. Step 0.3 (line 71) then gives "`<0.55` for 0.54" as the upper-bound example. This is the hallucination-trap pattern the repo's prompt rule forbids: if the read comes back empty, the nearest plausible token is the example. `uv.lock` currently says 0.54.0, so the example happens to match. Fix: remove the example and say "below the next minor of the version read in 0.1."

### [CONCERN] Backups sit outside the state directory, against a rule that names no exception

The Amoeba rule "config is config; state is state" puts databases in the state directory. D1 (line 148) and the departure table (line 578) put backups in a configured `backup_dir`, and task 9.1 (line 265) builds that. The design records the departure and its reason (another disk), but the rule has no exception. Either the rule is amended for backups (a rule change goes to the PM first), or the design keeps backups in the state directory and meets the other-disk need another way. Task 9.1 should be held until one of those is decided.

### [NOTE] hub.yaml load errors are typed two ways

Task 8.1 (line 241) says `load_hub_config` raises `HubConfigError`. Task 11.2a (line 314) says steps 2 to 7 "raise HubStartError with one line," and step 2 is the `hub.yaml` load. Both are operational, so exit 3 holds either way. Fix: state that step 2 re-raises `HubConfigError` and that `HubStartError` covers steps 3 to 7, so the 11.4 test asserts one type.

### [NOTE] The load test's CI gate is the existing Tests step

I checked that `ci.yml` line 40 runs bare `uv run pytest`, and that `pyproject.toml` line 64 ignores only `tests/live`. So `tests/load/test_door_load.py` is gated today. The Amoeba rule asks for a CI wiring task; 15.6 relies on the existing step and adds a collect-only check. That is explicit and acceptable. If the Tests step is ever narrowed, the gate disappears without notice.

### [NOTE] Certificate failure and connection failure are not distinguished

`ssl.SSLCertVerificationError` is a subclass of `OSError`. A retry loop that catches `OSError` for "no reply" would retry a certificate failure, which line 351 forbids. Test 12.4 should catch this, but the step should name the exception to check before the retry branch.

### [NOTE] The task file is large but does not need a split

The file is 480 lines with 17 sections and roughly 80 checkboxes. The section-end commit markers keep the commit units workable. Sections 13 and 15 are the heaviest. I would not split the file.

### [PASS] Success criteria trace to tasks, apart from the 261 item

All 23 functional bullets trace to a task or a test: the cross-machine standing, withdraw and decisions behaviour (15.2), `no_such_member` (15.2), certificate and join failures (12.4, 13.5), `bad_token` (15.3), repeats and the kill test (12.4, 15.5), `hub_fault` (10.2), the outage path (12.4), the no-client-file path (3.4, 7.4), joined entry points (14.4), door version (15.3), restarts and `--from-backup` (15.4), start refusals (11.4), noise (15.5), backup failures (9.2, 11.4), keep counts (9.2, 15.4), set-aside and leave (13.5), the acting machine (10.2, 15.4) and `update_live` (17.2). The technical requirements map to 0.2, 15.6 and 17.4.

### [PASS] Sequencing and commit cadence hold

There are no dependency cycles, and each test subsection follows its implementation. Sections 2 and 3 share one commit, which line 106 explains: migration 011 breaks inserts until 3.2. Commit markers sit at working points, not after every task. Apart from the findings above, the sequencing is sound.

### Run Digest

- Response length: 12130 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 976024 / 745199 / 230813 / 81990 / not computed
- Duration: 357.9 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
