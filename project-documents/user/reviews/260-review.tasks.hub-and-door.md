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
reviewedSha: 3560d53b333c0ea0b203aa48c623aa402ad2bd1b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
effort: xhigh
turns: 25
promptTokens: 1358482
cachedTokens: 1133081
cacheWriteTokens: 225385
completionTokens: 78983
durationSeconds: 353.2
costUsd: 0.464012
costBasis: provider
runId: run-20261121-p5-613fe239
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: uncategorized
    summary: "A `join` re-run after a crash between `hello` and the client-file write is refused"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:341"
  - id: F002
    severity: concern
    category: uncategorized
    summary: "A store at the store path beside a set-aside store has no exit"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:235"
  - id: F003
    severity: concern
    category: uncategorized
    summary: "\"Repeat under the same id\" needs a call-id seam the task does not provide"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:323"
  - id: F004
    severity: concern
    category: uncategorized
    summary: "The running hub's periodic backup check has no test"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:300"
  - id: F005
    severity: concern
    category: uncategorized
    summary: "11.2 is too large for one task and will push `hub/serve.py` past ~300 lines"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:297"
  - id: F006
    severity: concern
    category: uncategorized
    summary: "The mode-switch branch goes into `wiring.invoke`, against \"wiring.py gains only calls\""
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:338"
  - id: F007
    severity: concern
    category: uncategorized
    summary: "17.2's test must inject the `Steps` seam, or it reinstalls the tool"
    location: "scripts/update_live.py:292"
  - id: F008
    severity: concern
    category: uncategorized
    summary: "CI gating of the load test is implicit"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:396"
  - id: F009
    severity: concern
    category: uncategorized
    summary: "Backups live outside the state directory, against the Amoeba rule"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:148"
  - id: F010
    severity: concern
    category: uncategorized
    summary: "0.1 gates the whole slice on a file that does not exist and on Docker"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:61"
  - id: F011
    severity: note
    category: uncategorized
    summary: "A version example sits next to its own retrieval (hallucination trap)"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:63"
  - id: F012
    severity: note
    category: uncategorized
    summary: "Failure behaviour of `hub invite` before first start is not stated"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:361"
  - id: F013
    severity: note
    category: uncategorized
    summary: "Scope of \"every test module that inserts records\" in 3.4 is undefined"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:139"
  - id: F014
    severity: note
    category: uncategorized
    summary: "The design's walkthrough conclusion is wrong"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:732"
  - id: F015
    severity: pass
    category: uncategorized
    summary: "The success criteria are covered"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:626"
  - id: F016
    severity: pass
    category: uncategorized
    summary: "Commit markers and test placement are sound"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:145"
  - id: F017
    severity: pass
    category: uncategorized
    summary: "The repo facts the tasks rely on check out"
    location: "uv.lock:849"
---

# Review: tasks — slice 260

**Verdict:** FAIL (all findings resolved 20261121 in the task file and design; the two concerns aimed at the design are resolved there: D4 and the Departures table)
**Model:** claude-haiku-5-5

## Findings

### [FAIL] A `join` re-run after a crash between `hello` and the client-file write is refused

The design says that after a partial `join --set-aside-local`, "running the same join again also finishes it" (slice design line 229), and the walkthrough says to run the same command again (line 729). Task 13.2 instead says `set_aside` "refuses, naming both, when a set-aside store already exists". D4 refuses only when a set-aside store sits beside a local store. In the partial state there is no store at the store path, so `set_aside(store, …)` has no store to take. Task 13.3 (line 346) says nothing about this case, and 13.5 tests only `leave` resuming. A literal implementation refuses the re-run, which leaves the operator with no command to finish. Fix: state that `set_aside` with no store at the store path and a set-aside present is a no-op, so `join` continues to the client file. Add a 13.5 test that a `join` stopped after the rename is finished by a second `join`.

### [CONCERN] A store at the store path beside a set-aside store has no exit

Both `join` (D4, line 229) and `leave` (line 235) refuse and change nothing when both files exist. No command ends that state. It can arise from restoring a state-directory backup over a joined home, and then the only way out is moving files by hand. The Amoeba rule requires every state to have an exit with nobody editing files. Name an exit in the design, such as `leave` moving the existing store to a dated name, or say why the state cannot arise and what the message tells the operator. Tasks 13.2 (line 342) and 13.5 (line 353) currently lock in the refusal.

### [CONCERN] "Repeat under the same id" needs a call-id seam the task does not provide

12.3 gives `call(client_file, cert_path, name, document, times=DoorTimes())` no call-id parameter, and the id is generated inside. Tests 12.4 (line 329) and 15.5 (line 393) must repeat the call "under the same id" after a dropped reply or a kill, and nothing in the signature allows that. Add an optional `call_id` parameter that defaults to a new `uuid4().hex`, or name the seam the test uses. The test must not patch `uuid` globally.

### [CONCERN] The running hub's periodic backup check has no test

D14 step 9 and D15 require the serving hub to take a timed backup when one is due, and to log a failure and retry at the next check. 11.4 covers only start-time behaviour, and 15.4 asserts that restarts take no new backup. Nothing shows the loop taking a backup while serving, or retrying after a failure. Add a test that patches `BACKUP_CHECK_SECONDS` and `backup_hours` to small values and checks that a timed backup appears without a restart. Also check that a failing backup is logged and retried.

### [CONCERN] 11.2 is too large for one task and will push `hub/serve.py` past ~300 lines

One task covers prepare steps 2 to 8 (six refusals, the certificate, the `--from-backup` copy, the pre-migration backup and the store open), serve step 9 with uvicorn, the periodic backup task, and the stderr line. That is more than one module's worth of logic. 17.4 catches the size only at the end. Split it into 11.2a (prepare, in its own module) and 11.2b (serve and the backup loop), each with its tests in 11.4.

### [CONCERN] The mode-switch branch goes into `wiring.invoke`, against "wiring.py gains only calls"

The Context Summary (line 41) and 7.4 (line 224) say `wiring.py` gains only calls into `wiring_door.py`. 13.1 puts the branch in the first line of `invoke`: "when joined, a served operation goes through `client.call`… and any other raises `NotServedError`". `wiring.py` is already about 325 lines. Make 13.1 a single call into `wiring_door`, with all the branching there.

### [CONCERN] 17.2's test must inject the `Steps` seam, or it reinstalls the tool

`update()` (line 224) calls `steps.install`, which runs `uv tool install --force --reinstall` (lines 246 to 249). It also calls `steps.migrate` (`amoeba list`) and `steps.list_tools` (starts `amoeba-mcp`). `PRODUCTION` (line 292) binds the real ones. `main()` also runs `check_checkout` and `running_servers`. Task 17.2 (task file line 421) says only "against a copy … in a throwaway home". A test that drives `main()` or `PRODUCTION` would reinstall the tool on the PM's machine. Specify that the test calls `update()` and `restore()` with a fake `Steps`, that `migrate` opens the copied store through `Store.open` so the schema-11 check can pass, and that `AMOEBA_HOME` names the throwaway home.

### [CONCERN] CI gating of the load test is implicit

`.github/workflows/ci.yml:40` runs a bare `uv run pytest`, and `pyproject.toml:59` sets `testpaths = ["tests"]`. Only `tests/live` is ignored (line 64), so the new `tests/load` file will run in CI. No task says so, and the design says only "runs in the normal tier and in CI". The 2 s and 200 ms bounds are timing assertions on a shared `ubuntu-latest` runner. Add a step to 15.6 that confirms the default run collects the file, and say what to do if it is flaky, or add an explicit CI gate.

### [CONCERN] Backups live outside the state directory, against the Amoeba rule

D1 makes `backup_dir` (a configured path with no default) the one piece of state outside the state directory. The Amoeba rule says databases and run records live in the state directory. D1 gives a reason (a different disk), but the exception is missing from the Departures table and not flagged for PM decision. Raise it with the PM, or make the default a path under the state directory that stays overridable. Tasks 8.1 (line 240) and 9.1 depend on the choice.

### [CONCERN] 0.1 gates the whole slice on a file that does not exist and on Docker

The glob `260*` in `project-documents/user/tasks/` returns only `260-tasks.hub-and-door.md`, so "both task files" (line 61) cannot be satisfied. Line 62 also makes a missing `docker version` a BLOCKED condition for section 0, which stops sections 0 to 15 for a need that only 16.2 has. Blocked work should not stop unrelated work. Remove "both task files", and move the Docker check into 16.2.

### [NOTE] A version example sits next to its own retrieval (hallucination trap)

0.1 says "uvicorn 0.54" beside the instruction to note the locked version, and 11.2 (line 301) compares against 0.54. `uv.lock:849` says 0.54.0, so nothing is wrong today. Under the prompt rules, reword it so the retrieval has no nearby example: note the version from its `uv.lock` entry, BLOCKED if the entry is missing, and compare against the version D14 records.

### [NOTE] Failure behaviour of `hub invite` before first start is not stated

`invite` needs `hub.yaml` for the address and the certificate for the fingerprint. 14.1 says nothing about either missing. Say that it fails and names the missing file, and that it changes nothing.

### [NOTE] Scope of "every test module that inserts records" in 3.4 is undefined

The grep finds 114 files that use `Store.open`, not "about 115". Which modules count as inserting is not defined. The baseline check bounds the work, so the task still works. Say "replace in every test module except the named migration and open tests" to remove the judgement call.

### [NOTE] The design's walkthrough conclusion is wrong

"Dead ends found: none" is contradicted by the join re-run dead end and the both-files state above. Correct the design once those findings are resolved.

### [PASS] The success criteria are covered

All 23 functional requirements, the technical requirements (ruff, pyright, import rules, load bounds, file size, contract docs) and the integration requirements map to tasks. Each has a test or a stated check. The gaps are the findings above.

### [PASS] Commit markers and test placement are sound

There are 16 markers at working points. Sections 2 and 3 correctly share one commit, because the suite fails between them. Every implementation section ends with its tests.

### [PASS] The repo facts the tasks rely on check out

`uvicorn` 0.54.0, `starlette` 1.10.0 and `cryptography` 50.0.2 are locked. `anyio` is already declared (`pyproject.toml:9`), so 11.1's import needs no new dependency. The 16 insert statements in 3.2 are complete, with no `INSERT OR` or `REPLACE INTO` elsewhere. `read_schema_version`, `BUSY_TIMEOUT_SECONDS`, `OPERATIONAL_ERRORS`, `MoveHooks`, `Store.write`/`read` and the autouse `AMOEBA_HOME` fixture exist. The logs directory sits under the state home, which matches D1. The docs and the Docker guide the tasks name exist.

### Run Digest

- Response length: 11303 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 1358482 / 1133081 / 225385 / 78983 / not computed
- Duration: 353.2 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
