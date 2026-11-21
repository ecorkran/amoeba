---
docType: review
layer: project
reviewType: slice
slice: adoption
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS (reviewer stated FAIL; its fail findings were fixed; all sixteen findings were checked 20261120; fifteen changed the design, one was dropped, see Resolution)
verdictSource: stated
sourceDocument: project-documents/user/slices/264-slice.adoption.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 005a288700625ad5fc4874ea1408fe3caec125a7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 1685479
cachedTokens: 1418932
cacheWriteTokens: 266527
completionTokens: 135811
durationSeconds: 621.6
costUsd: 0.664251
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: architecture-boundary
    summary: "The client-file guard is removed while three commands open the local store with a client file present"
    location: "project-documents/user/slices/264-slice.adoption.md:328"
  - id: F002
    severity: concern
    category: state-exit
    summary: "`discard-local` is blocked once the machine has no client file, so a handed-over store has no exit after `leave`"
    location: "project-documents/user/slices/264-slice.adoption.md:300"
  - id: F003
    severity: concern
    category: architecture-boundary
    summary: "Three changes to parent behavior are missing from the departures table"
    location: "project-documents/user/slices/264-slice.adoption.md:236"
  - id: F004
    severity: concern
    category: architecture-boundary
    summary: "The door departs from its stated shape, and the new time values sit outside the pinned tuple"
    location: "project-documents/user/slices/264-slice.adoption.md:240"
  - id: F005
    severity: concern
    category: failure-modes
    summary: "The lock-hold bound \"at most 239 seconds\" does not hold"
    location: "project-documents/user/slices/264-slice.adoption.md:128"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "A failed post-load count check replaces the hub's store with no kept copy"
    location: "project-documents/user/slices/264-slice.adoption.md:274"
  - id: F007
    severity: concern
    category: error-handling
    summary: "A set-aside store with a client file is told to run `--again`, which the design refuses while a client file exists"
    location: "project-documents/user/slices/264-slice.adoption.md:157"
  - id: F008
    severity: concern
    category: failure-modes
    summary: "Laptop-side I/O failures get one generic line, and `add-config-keys` writes in place"
    location: "project-documents/user/slices/264-slice.adoption.md:168"
  - id: F009
    severity: concern
    category: test-coverage
    summary: "The test guarding \"no `cf` under the write lock\" is deleted on a rationale that no longer holds"
    location: "project-documents/user/slices/264-slice.adoption.md:357"
  - id: F010
    severity: concern
    category: risk
    summary: "Installing the PM's store before code review makes a review fix to migration or load cost a re-adoption that loses hub records"
    location: "project-documents/user/slices/264-slice.adoption.md:436"
  - id: F011
    severity: concern
    category: proportionality
    summary: "The design restates the parent in several places and keeps two copies of the config example"
    location: "project-documents/user/slices/264-slice.adoption.md:462"
  - id: F012
    severity: note
    category: scope
    summary: "The legacy-store check keeps a file test the architecture deletes"
    location: "project-documents/user/slices/264-slice.adoption.md:331"
  - id: F013
    severity: note
    category: state-exit
    summary: "`discard-local` deletes the only pre-migration backup, which the architecture names as the fallback"
    location: "project-documents/user/slices/264-slice.adoption.md:300"
  - id: F014
    severity: note
    category: documentation
    summary: "Principle amendments land in this slice's first task, so the design is reviewed against a parent it changes"
    location: "project-documents/user/slices/264-slice.adoption.md:423"
  - id: F015
    severity: note
    category: dependency-direction
    summary: "`wiring_door` depends on `wiring_adopt`, the module that reaches the local store"
    location: "project-documents/user/slices/264-slice.adoption.md:110"
  - id: F016
    severity: note
    category: documentation
    summary: "The walkthrough's \"Dead ends found: one\" is incomplete"
    location: "project-documents/user/slices/264-slice.adoption.md:651"
  - id: F017
    severity: pass
    category: architecture-alignment
    summary: "The hub-side load follows the architecture's transaction rule"
    location: "project-documents/user/slices/264-slice.adoption.md:260"
  - id: F018
    severity: pass
    category: nfr
    summary: "NFRs are restated with targets"
    location: "project-documents/user/slices/264-slice.adoption.md:364"
  - id: F019
    severity: pass
    category: integration
    summary: "Interfaces match what 260–263 decided"
    location: "project-documents/user/slices/264-slice.adoption.md:77"
---

# Review: slice — slice 264

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The client-file guard is removed while three commands open the local store with a client file present

D7 deletes 260's guard, which raises `LocalStoreClosedError` when a store opener runs with a client file present (260 slice, line 172). The stated reason is "Nothing opens a local store to guard." That is false. Adopt's rows 4 and 5 open the store to compute its digest on a machine that has a client file (lines 159–160, 164). `discard-local` for an adopted store calls `adopt_check` through the client file and then reads the store's digest (line 300). Architecture `260-arch.the-hub.md:223` says "With a client file, no local store is ever opened or created." The design departs from that without a departures-table row. The guard exists so a missing file is never recreated. SQLite creates a file when it opens a missing path, and D2 and D5 never say the handover opener checks that the path exists first, including for `discard-local` and `join --set-aside-local`. Fix: keep the guard for every opener except `store.handover`, have `handover` check existence before opening and never create, add a departures row, and test each new command in a client-file home for "no file created."

### [CONCERN] `discard-local` is blocked once the machine has no client file, so a handed-over store has no exit after `leave`

D5 names `discard-local` as the way a handed-over store ends. D6 (line 314) and success criterion line 535 say every CLI command except `join`, `adopt`, `leave` and `hub` fails with `NotJoinedError` without a client file, and `discard-local` is not exempt. `leave` removes the client file, and the undo paths tell the PM to run it first (line 411). After `leave`, the stated exits are `adopt --again`, which needs a hub line, or joining some hub in order to reach `discard-local`. For a set-aside store, `discard-local` needs no hub call at all. Fix: allow `discard-local` without a client file for a set-aside store, and state what an adopted store needs when no client file exists.

### [CONCERN] Three changes to parent behavior are missing from the departures table

- Architecture line 235 and plan line 157 say a hub is empty only when it holds "nothing but its owner and its invited machines." D3 counts only tables outside `HUB_OWN_TABLES`, so `sessions`, `machine_runs`, `call_results`, `closed_mark` and `adoption` do not make a hub non-empty. D1 (line 184) then drops the other machines' sessions and runs on load. Those rows are regenerable, but a joined machine's history is overwritten without a refusal.
- Architecture step 1 (line 235) puts the checks before anything changes. The design runs the session check at step 4, after migration 015 (lines 120, 204–205). A refused `adopt` has already migrated the store past the schema the laptop's programs read, so every session on the laptop loses its tools until the adoption completes or the session restarts. The walkthrough (line 625) says only "nothing has to be closed."
Fix: add departures rows for both, and either match the architecture's empty rule or name the exempt tables and why.

### [CONCERN] The door departs from its stated shape, and the new time values sit outside the pinned tuple

- D3 adds a non-JSON upload route (line 242). Architecture line 115 says "The door is HTTPS with JSON." The departure is not tabled. The upload's refusals (lines 248–249) are not stated as log lines, though architecture line 118 says a refused call is "refused and logged."
- Line 240 keeps `ADOPT_READ_SECONDS` and `UPLOAD_IDLE_SECONDS` out of 260's pinned tuple and says the door version does not change. Architecture line 127 says "A change to one of these constants changes the door version." 260 slice line 309 pins the time values with `DOOR_VERSION`, and 263 bumped the version when it added `MCP_CALL_DEADLINE_SECONDS` to the tuple (263 slice line 479). The client read time and the hub idle time do not need to agree with each other, so the pin may not be needed, but the design must say so and record the exception.
Fix: add both constants to the tuple and bump the version, or record the exception with its reason, and state that upload refusals are logged.

### [CONCERN] The lock-hold bound "at most 239 seconds" does not hold

The bound adds retry, connect and read times for each of the three calls. None limits how long the upload body takes to send, and line 242 says "There is no fixed size limit." The hub's idle limit (30 s, line 252) cuts only a connection that sends nothing. A slow but steady upload holds the laptop's write lock for as long as it runs, and nothing caps the total. Fix: give the upload a total deadline derived from the constants and the body size, or call the figure a per-stall bound and state what happens when the total is reached.

### [CONCERN] A failed post-load count check replaces the hub's store with no kept copy

Step 5 replaces the hub's store in one backup call, and step 6 compares counts afterward. Line 278 says a mismatch "should not be possible," then refuses with the instruction to restart the hub on an empty state directory. That destroys every record on the hub, including other machines' writes since the first attempt. D10 (line 391) already keeps a replaced store in `replaced-<stamp>/` for a failed update, so the same step could keep the pre-load store here. The walkthrough (lines 620–651) does not cover this state. Fix: move the pre-load store to `replaced-<stamp>/` before step 5, name that path in the refusal, and add the state to the walkthrough.

### [CONCERN] A set-aside store with a client file is told to run `--again`, which the design refuses while a client file exists

Row 2 of D1 rejects `adopt` for a set-aside store "with or without a client file" and names `--again`. Line 166 says `--again` "is rejected when a client file exists." The message sends the PM to a command that will refuse. The only exit is `amoeba leave` first, which the message does not mention. Success criterion line 520 covers the case without giving the path. Fix: when a client file exists, the row 2 message names `amoeba leave`, then `--again`.

### [CONCERN] Laptop-side I/O failures get one generic line, and `add-config-keys` writes in place

Line 168 covers every laptop failure with "exit 3, lock released, run again." It does not say what happens on a disk-full or failed write to the pre-handover backup or the copy, both of which precede any mark. It also does not name a failed client-file write after the mark, which leaves a marked store with no client file. That state is covered only implicitly by row 5 of D1. `hub add-config-keys` (line 396) appends keys "at the end of the file" with no temporary file and rename, unlike `adopt_config` (line 258), and gives no failure mode for a crash or full disk partway through. Fix: list each new laptop I/O path with its handling, and have `add-config-keys` write through a temporary file and rename.

### [CONCERN] The test guarding "no `cf` under the write lock" is deleted on a rationale that no longer holds

D9 deletes the no-`cf`-under-write-lock test because "the hub's `PATH` holds no `cf`." The risk is on the laptop. Adopt runs `cf` for the naming fix (D2), and the laptop's store lock is held for up to 239 seconds (line 128). Slice 261 keeps `cf` gathering outside the write lock (261 slice line 219), and that is the invariant this test protects. Fix: keep the test and point it at the lock window in `adopt_local`.

### [CONCERN] Installing the PM's store before code review makes a review fix to migration or load cost a re-adoption that loses hub records

D12 runs the live install "from the slice branch, before code review and the merge." The design's own remedy for a review finding in migration 015, the fixes or the load is to adopt again, which discards everything recorded on the hub since the first adoption (lines 436–439). The plan rates this slice high-risk because it moves the live store (260 slices, line 168). Fix: run the live install after review of the adoption path, with the fixture rehearsal (lines 425–434) as its precondition.

### [CONCERN] The design restates the parent in several places and keeps two copies of the config example

Cut candidates, none needed for the stated requirements:
- "Amendments to 260 and 263" (lines 462–474) restates D5–D8 and overlaps the departures table. Keep one list.
- The config example exists as a wheel file (D10) and as the contract's block, kept equal by a test (line 398). Keep the file and have the contract link it, with no equality test.
- The verification walkthrough (lines 556–584) repeats D9's file names.
- The departures table (lines 441–460) restates D1–D8. A row naming the decision number is enough.
The digest in D1 is not a cut: counts cannot see a changed row (line 180).

### [NOTE] The legacy-store check keeps a file test the architecture deletes

Architecture line 54 deletes the 228 state move, and D7 keeps one file test for the pre-228 path. Checked on this machine: `~/.config/amoeba` holds only `config.yaml`, which matches D7's claim about the PM's laptop. The design does not say whether any other machine can still have a pre-228 store. Keep the check if one can; otherwise cut it with `legacy_state_home`.

### [NOTE] `discard-local` deletes the only pre-migration backup, which the architecture names as the fallback

Architecture line 252 calls the laptop's dated backup "the fallback for one case only." D5 has `discard-local` delete every `backups/pre-handover-*` directory, so the first run removes the last copy of the pre-migration store. That is consistent with the exit rule. The command should print the paths it is about to delete, not only after.

### [NOTE] Principle amendments land in this slice's first task, so the design is reviewed against a parent it changes

D12 amends the architecture's principles and the plan's 264 criteria in the slice's first task, after design review. This review therefore judged the departures against the unamended parent. Land the amendments in the parent before the design is approved, or name in the design the parent text each departure replaces.

### [NOTE] `wiring_door` depends on `wiring_adopt`, the module that reaches the local store

D1's import rules let `wiring_door` call `wiring_adopt` for the store part of `--set-aside-local`. That makes the door's wiring depend on the local-handover path, and the design does not say which door operation needs it. Name the operation, or move the call into `join_command`.

### [NOTE] The walkthrough's "Dead ends found: one" is incomplete

Missing from the walkthrough: the set-aside case with a client file (line 157), the post-load count failure (line 278), and `discard-local` after `leave` (line 300). Line 644 says a failed laptop update "puts the laptop back," but D10 (line 382) says a door-version change leaves the reinstalled laptop refusing every command until it is updated.

### [PASS] The hub-side load follows the architecture's transaction rule

Each hub step is one write transaction or a file operation. Every writer checks the loading mark (line 280), the load runs in worker threads (line 244), and the hub never reads a client's disk. This matches `260-arch.the-hub.md` lines 58–64.

### [PASS] NFRs are restated with targets

The door load test bounds are restated: calls inside 2 seconds with 16 clients, median under 200 ms on an idle hub (line 364). Ticks during a slow upload or the load must be answered inside 2 seconds (line 284).

### [PASS] Interfaces match what 260–263 decided

Checked against the source slices: 263 D1 (mode decided per tick, so a session started before joining uses the hub from its next tick); 263 D4 (a refused tick is skipped); 260's `CALL_BOUND_SECONDS` of 43, which equals 30 + 3 + 10 and matches the design's 239-second arithmetic; 261 D4 (member naming gathers `cf` before taking the write lock). Scope matches the 264 plan entry, except for the weakened empty-hub rule above.

### Run Digest

- Response length: 14169 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 1685479 / 1418932 / 266527 / 135811 / not computed
- Duration: 621.6 s
- Cost: $0.66 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19

## Resolution

Resolved 20261120 in `user/slices/264-slice.adoption.md`. Each finding was checked against the design and the documents it cites. Slices 260 to 263 are not built yet, so there was no hub code to check against; today's `store/store.py`, `store/migrations.py`, `config/user_config.py` and `scripts/update_live.py` were read. Nothing was deferred and no issue was filed.

- [fail] The client-file guard is removed while three commands open the local store with a client file present: changed. Valid: "Nothing opens a local store to guard" was false, and nothing said the hand-over opener must not create a store (`Store.open` creates one today). D5 now says `store.handover` tests that the file exists and opens with SQLite's `mode=rw`, or `mode=ro` for the digest reads, so a joined machine's `adopt` and `discard-local` never write the store and nothing creates one. Tried 20261120 on SQLite 3.50.4. D7, the departures table, the 260 amendments and a "no file created" criterion are updated. The other guarded opener is deleted, so there is no guard to keep.
- [concern] `discard-local` is blocked once the machine has no client file: changed. `discard-local` runs without a client file (D6) and `--force` deletes with no hub call (D5). One rule replaces the two `--force` cases: without `--force` it deletes only when the joined hub holds the adoption and the digest is unchanged.
- [concern] Three changes to parent behavior are missing from the departures table: changed. Rows added for the empty-hub rule and for the session check running after the migration. D2 and the walkthrough now say a refused `adopt` leaves the store migrated and older sessions' tools failing until the machine is joined. The exempt tables stay: a joined machine writes them by itself.
- [concern] The door departs from its stated shape, and the new time values sit outside the pinned tuple: changed. Departures rows added for the non-JSON route and for the two times outside the tuple, with the reason in D3. D3 says upload refusals are logged.
- [concern] The lock-hold bound "at most 239 seconds" does not hold: changed. The arithmetic was right (43 + 153 + 43) but nothing bounded the time to send the body. `ADOPT_READ_SECONDS` is now `ADOPT_UPLOAD_SECONDS`, 120, the longest one whole attempt may take, sending and waiting. An attempt that reaches it is stopped, and a store too large to send in that time fails with its size and the time allowed.
- [concern] A failed post-load count check replaces the hub's store with no kept copy: changed, by removing the check. The counts are checked in step 4 on the file that step 5 copies in one SQLite call, so the later check could only fail with the store already replaced. `copy_damaged` now always means the hub's store is as it was. The finding's premise that other machines' records would be lost was wrong: a load only runs into a hub with no records of its own, or one unchanged since the first load. Separately, "start the hub on an empty state directory" became a command, `hub-restore.sh --empty`, which keeps what the hub held.
- [concern] A set-aside store with a client file is told to run `--again`: changed. Rows 2 and 3 of D1 and the `--again` rejection name `amoeba leave` first when a client file exists. Criterion and walkthrough updated.
- [concern] Laptop-side I/O failures get one generic line, and `add-config-keys` writes in place: changed. Data Flow says what a failed backup, copy, client-file write and rename each leave. The local `config.yaml` is loaded before anything is written. `add-config-keys` writes through a temporary file and a rename.
- [concern] The test guarding "no `cf` under the write lock" is deleted: changed. The test is kept and pointed at `adopt`, whose naming fix is the one place `cf` and a local write lock still meet. Only its `report_release` case goes.
- [concern] Installing the PM's store before code review: changed, as the PM ruled. The install task is gone. The release adopts the PM's store, after review and the merge, through a first-run path in `update_live.py update` that sets the hub up, gets the join line, adopts, reads back, and puts the laptop back by itself on failure (D10, D12). The slice proves the path on fixtures and by a rehearsal on a copy of the live store.
- [concern] The design restates the parent in several places and keeps two copies of the config example: no change. The two tables serve different readers (the parents, and the sibling designs), and the equality test is one assertion that stops the contract's example drifting from the shipped file.
- [note] The legacy-store check keeps a file test the architecture deletes: changed. One sentence added to D7: Amoeba is on PyPI, so an install that is not the PM's can still have a pre-228 store. The check stays.
- [note] `discard-local` deletes the only pre-migration backup: changed. It prints each path before deleting it, and its output says neither undo in D11 is possible afterwards. It still deletes the backup, which is what the command is for.
- [note] Principle amendments land in this slice's first task: changed. The task is removed. D12 says the parents hold the amendments as of 20261120; the exact text for `260-arch.the-hub.md` and `260-slices.the-hub.md` was reported with this resolution, to be applied the same day.
- [note] `wiring_door` depends on `wiring_adopt`: changed. Only `join_command` calls `wiring_adopt`, and the import rule says `wiring_door` does not import it.
- [note] The walkthrough's "Dead ends found: one" is incomplete: changed. The walkthrough is rewritten from a laptop with a local store to a laptop that is a client, with each cut-off and each way back, and lists the nine dead ends found and closed. Three were not in this review: `discard-local` cut off after deleting the store, the way back to the local store being four steps by hand, and `hub-restore.sh` putting back a `config.yaml.before-keys` from an earlier update.
- [pass] The hub-side load follows the architecture's transaction rule: no change.
- [pass] NFRs are restated with targets: no change.
- [pass] Interfaces match what 260–263 decided: no change.

## Full-text review, 20261121

A second review read the whole design, start to finish, with the architecture, the slice plan, the 260 design in full, the cited sections of 261 to 263, and today's `scripts/update_live.py`, release skill, `store/store.py`, `store/migrations.py`, `store/sql_sessions.py`, `config/home.py` and the migration tests. It ran the design's two SQLite sequences in a scratch database, and both hold as written. It found 19 things: 8 important, 10 minor and 1 unverified. All 19 are resolved in the design the same day, together with what 260's revision of 20261121 (commit 9ee28aa5) changed under it. None ended as "no change". The parents were not edited; the sentences they still need are listed at the end.

- [important] `restore --local-store` restored the oldest backup, which could be older than the laptop's records or a partial copy: changed (D5, D11). The command reads the store's schema first and leaves a store below 15 alone. A backup is taken only when the store is below 15, under a `.partial-` name, and a new whole one deletes the older ones, so the one kept is the store just before the migration that closed it.
- [important] An `adopt` refused before its backup left the new release installed over a local store: changed (D10, D11). `update` runs `adopt` from the checkout before it installs, and the script's restore installs the previous commit whatever the store's state.
- [important] `update` run again after a kill failed at its own `amoeba list -j`: changed (D10). The script writes `backups/adoption-run.json` before the adoption and uses it when it finds the store already migrated. D1's row 4 takes a new invite's token.
- [important] The first-run `hub.yaml` could not hold the hub's address: changed (D10, D12). `live-update.yaml` gains the required key `hub_address`; `hub-update.sh --address` writes it on a first run and replaces it on a later one. D12 says what the localhost rehearsal proves about the address and what is first met at the release.
- [important] A store set aside after a failed `adopt` was reported as `already_adopted`: changed (D1, D5). `join --set-aside-local` deletes the adoption row with the mark.
- [important] Whether the laptop's `sessions` and `machine_runs` rows are carried was contradictory, and the count check could not pass on a second load: changed (D4, criteria). The load deletes the copy's `sessions`, `machine_runs` and `call_results` rows and compares counts only outside `HUB_OWN_TABLES`.
- [important] `hub-restore.sh` did not say which pre-migration backup it restores or how its one start ends: changed (D10). `hub-update.sh` lists the backups before the new image starts; the restore uses only one not listed, makes 260's `docker compose run ... --from-backup` start, waits for the serving line for at most `RESTORE_START_SECONDS`, and then deletes the list.
- [important] The digest, counts and emptiness check needed SQL built from table names read at run time: changed (D3). `STORE_TABLES` is a module constant pinned to the schema by a test, and header keys are checked against it.
- [minor] "A second run takes no second copy" was false after a failure in step 4: changed (D5), by the schema rule above.
- [minor] After a failed adoption the hub held the copy and every later `update` was refused until the hub was emptied by hand; the read-back compared two listings field by field: changed (D10, D11). The restore keeps the adoption id in `kept-adoption-id`, so the next attempt meets `holds_this`. The read-back compares the number of programs and members and prints the rest.
- [minor] The earlier script's `backups/<stamp>/` was never removed: changed (D10). The first `update` that succeeds deletes it.
- [minor] The mark and the id are read before the tables exist: changed (Data Flow, step 2). A missing table means none, read read-only.
- [minor] Clearing the loading mark is itself a refused write, and the copy's side files were not named: changed (D4, Data Flow). The clear uses a plain connection, and "the copy" includes its two side files.
- [minor] `--again` on a store cut off before its switch stranded it: changed (D1). It is rejected and names `adopt`.
- [minor] Four small false statements about today's script and `legacy_state_home`: changed (D7, D10, D11, API Contracts). `--previous` is kept.
- [minor] "At the current schema" did not hold for later releases: changed (D5). The read-only open makes no schema check.
- [minor] Three parent sentences are stale: changed in the design's departures table (rows dated 20261121); the parents' text is listed below.
- [minor] Two `adopt` runs at once had no rule: changed (D5). One hand-over command runs at a time, under a file lock.
- [unverified] "Built by the seed helpers at schema 10": confirmed false and changed (D9). The seed helpers write the current schema; the fixture is built as `_migrate_to` in `tests/store/test_migration_010.py` does.

From 260's revision: D5, D7 and the amendments table describe the set-aside from its copy form, and `discard-local --force` ends a `set-aside-<stamp>` store left by a release from 260 to 263. `--put-back` and `--discard` end every `replaced-<stamp>/`, including 260's own. `hub-restore.sh --empty` is checked against 260's start table and moves the store before the backups. The hub side of the load opens the store without creating it. `store.handover` keeps the `HubHomeError` check, and the example compose file's directories are under `~/amoeba-hub/`.

Changes this needs outside the design, not made here:

- `260-slices.the-hub.md`, Planning Context, third bullet: "So adoption in 264 is a copy, not a migration." should read "Adoption in 264 migrates the laptop's store itself and then copies it."
- `260-slices.the-hub.md`, 264 entry, The PM's install: add "`live-update.yaml` names the three hub commands and `hub_address`."
- `260-arch.the-hub.md`, Moving the PM's live store, first paragraph: "By this point the laptop's store is already at the new schema and its members are named, so the move is a copy." should read "`adopt` brings the laptop's store to the new schema and names its members first, so what is sent is a copy."
- `260-arch.the-hub.md`, Operator walkthrough, step 1: "write `hub.yaml` in the config directory (the image ships an example) and start the container" should read "`docker/hub-update.sh --address <host:port> <commit>` writes `hub.yaml` from the example and starts the container; the release runs it".
- `260-arch.the-hub.md`, Moving or undoing the hub: after "puts the pre-migration backup and the config back under the previous release" add "when `adopt` had migrated the store; a store the previous release still opens is left as it is".
- `260-slice.hub-and-door.md`, D4, last paragraph on 264: add that `join --set-aside-local` also deletes the adoption row, and that a `set-aside-<stamp>` store left by this slice's form is ended by 264's `discard-local --force`. D17: the example compose file's host directories are under `~/amoeba-hub/`.

### Second pass

A second pass on 20261121 read the fixed design in full and walked the pieces the fixes above added: the record, the kept id, the handover lock, the hub's backup list. One sequence was tried in a scratch directory (SQLite's backup call onto a write-locked store). Each defect and what was done:

- [important] `restore --local-store` wrote the store outside the handover lock, and a second `update` ran it under the first one's `adopt`: changed (D5, D10, D11). `update` and `restore` hold `update.lock`; the restore takes the handover lock; an `adopt` that meets `HandoverBusyError` is not followed by a restore; `leave` skips the copy while a hand-over command runs.
- [important] A record left by a failed or killed `update` made a later `update` un-join a laptop whose store had been set aside by hand: changed (D10). A run that fails before `adopt` deletes its record, and a record beside a set-aside store or no store is deleted and the main list taken.
- [important] A kept adoption id beside a set-aside store could be read as the store's id: changed (D1, D5, D11). D1's rows read the store's own row only, and `join --set-aside-local` deletes the file.
- [important] `update` could not go on after its own restore was killed following the install, and "if another is installed" could not be decided: changed (D10, D11). A record beside a store below 15 makes `update` finish the restore first, and the record's commit is always installed again.
- [important] A read-back after a skipped load compared the hub's members with an older listing and named `hub-restore.sh --empty`: changed (D10). On a `skipped` run the numbers are printed, not compared; the bullet is deleted.
- [important] `update` run after a failed hub restore deleted `pre-update-backups`: changed (D10). `hub-update.sh` finishes a restore that did not finish before it deletes anything; `--empty` and `--put-back` delete the list before they move the store, so they never look like one.
- [minor] `restore` and `restore --hub` after the adoption run installed the release before the hub: changed (D10). The adoption run leaves no `backups/previous-commit`, and both commands stop without one and name `restore --local-store`. `installed-commit` is written before the record is deleted.
- [minor] `LIVE_SESSION` in 263 D13 leaves out rows with no door version, which `sessions_to_restart` must list: changed (D2, Interfaces Required, amendments table). This slice adds `FRESH_HEARTBEAT` and composes `LIVE_SESSION` from it.
- [minor] `add-config-keys` both "first copies" and "writes nothing": changed (D10). It copies only when it has a key to add and no `config.yaml.before-keys` exists.
- [minor] `backups/previous-commit` and `installed-commit` were not in State Management: changed.
- [minor] "A missing `config.yaml` is written from `config.yaml.example`" had no subject: changed (D1). The message gives the copy command; `adopt` writes no local config.
- [minor] `--again` "is already at this release's schema" did not hold for a later release: changed (D1, D5, D11). The rule stays "below 15", with the reason the records are safe: the backup from before the first migration holds every record, and "at 15" means 15 or above.
- [minor] A machine that left with a set-aside store was told only `adopt` or `restore --local-store`: changed (D10). The message also names `amoeba join <line>`.
- [minor] The adoption run had no step that added a required key to the laptop's `config.yaml`: changed (Data Flow step 3, D10). `adopt` completes the text in memory with the function behind `add-config-keys` and sends that; the laptop's file is not changed, so the previous release still loads it after a restore.

### Third pass

A third pass on 20261121 read the fixed design in full against the architecture, the slice plan, the cited parts of 260 to 263 and today's `scripts/update_live.py`, `store/migrations.py`, `wiring_presence.py`, `config/home.py` and `tests/store/test_migration_010.py`, and walked the release path for kills, stale files, two runs and runs again. The claims about today's code hold. Each defect and what was done:

- [important] After a finished adoption, `restore --local-store` left `backups/installed-commit` and `backups/previous-commit` naming hub-era releases. The next `update`'s record took that commit, so an `adopt` refused before it migrated was followed by a restore that installed a hub-era release over the local store; every later `update` then failed at its own `amoeba list -j`, and `restore --local-store` with no record installed nothing. Plain `restore` could also install `backups/previous-commit` over the local store. Changed (D10 step 2, D11, State Management, criteria): `restore --local-store` writes the commit it is restoring to `installed-commit` and deletes `previous-commit` before the store goes back; with no record it installs `installed-commit`; `update` always runs it first beside a store below 15, so a hand-run restore cut off before its install is finished too.
- [important] D1 said `--again` "takes no new backup, because the store is at schema 15 or above". After `restore --local-store` the store is below 15 and `--again` is accepted there, so an implementer following D1 would migrate it with no backup, and a later `restore --local-store` would put back the older backup over records written since. Changed (D1, criteria): `--again` follows D5's one test like every hand-over command.
- [minor] "Installs the commit in `previous-commit`" (criteria) and "install the previous commit" (D11) could be read as `backups/previous-commit`, which after later updates names a hub-era release. Changed: the backup's `previous-commit`, never `backups/previous-commit`.
