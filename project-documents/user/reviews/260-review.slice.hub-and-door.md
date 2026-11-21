---
docType: review
layer: project
reviewType: slice
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS (reviewer stated FAIL; its fail findings were fixed; all eleven findings were checked 20261120; nine were fixed in the design and two dropped, see Resolution)
verdictSource: stated
sourceDocument: project-documents/user/slices/260-slice.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 0555204e40c1f1b9400d6abf568d9944c43df9ea
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
effort: xhigh
turns: 15
promptTokens: 1323056
cachedTokens: 1135353
cacheWriteTokens: 187685
completionTokens: 92350
durationSeconds: 415.7
costUsd: 0.462598
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: scope
    summary: "The live-store migration is deferred to the release, against the plan"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:522"
  - id: F002
    severity: fail
    category: error-handling
    summary: "`amoeba leave` cannot restore a set-aside store as its steps are ordered"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:232"
  - id: F003
    severity: fail
    category: operations
    summary: "The walkthrough's lost-state recovery does not match the start sequence"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:687"
  - id: F004
    severity: concern
    category: specification
    summary: "The kill-between-commit-and-reply criterion is tested as a dropped reply"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:505"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Hub logging to stderr is not covered by D16's guarantee"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:487"
  - id: F006
    severity: concern
    category: error-handling
    summary: "The hub's inbound path has no timeouts or connection limit"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:266"
  - id: F007
    severity: note
    category: specification
    summary: "The owner is on 12 tables, but the architecture's Owner section lists 8"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:399"
  - id: F008
    severity: note
    category: specification
    summary: "Two plan departures are missing from the departures table"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:536"
  - id: F009
    severity: note
    category: scope
    summary: "Scope the plan assigns to later slices is not named"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:61"
  - id: F010
    severity: note
    category: architecture
    summary: "The client file's placement does not follow the test the design applies to the certificate"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:143"
  - id: F011
    severity: note
    category: scope
    summary: "Some parts could be cut without losing a requirement"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:264"
  - id: F012
    severity: pass
    category: architecture
    summary: "The served list and the mode switch match the plan and the architecture"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:160"
  - id: F013
    severity: pass
    category: architecture
    summary: "The trust model matches the architecture"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:251"
  - id: F014
    severity: pass
    category: specification
    summary: "NFRs are restated with targets, and the claims about existing code hold"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:619"
---

# Review: slice — slice 260

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The live-store migration is deferred to the release, against the plan

D19 and the departures table (line 542) move the live-store migration out of this slice and into the release run of `update_live.py`. The slice plan's 260 success criteria require the live store to be "backed up and migrated, with the restore path in the slice notes," and its Planning Context says schema changes "land on the local store as they come." The PM's 2026-11-14 designation already covers this migration, so nothing blocks it. The design's reason, "live updates ride with the release," is not in any rule given to this review, and the Amoeba design rules say a review that finds a deferral rejects it. Either run `update_live.py update` in this slice as the plan says, or have the PM change the plan criterion first.

### [FAIL] `amoeba leave` cannot restore a set-aside store as its steps are ordered

Step 1 of `leave` clears the closed mark and renames the set-aside store back. Step 2 deletes the client file. Line 238 says step 1 runs while the client file still exists. Line 172 says both store openers raise `LocalStoreClosedError` whenever the client file exists, with no exception for `leave`. Clearing the mark is a write to the store, so as written `leave` fails at step 1 on any joined machine that set a store aside. That leaves the joined state with no exit, which breaks the rule that every state has one. Fix the order, so the client file is deleted first and step 1 runs after, which stays resumable because the local opener already refuses to create a store in that state (line 228). Or name the guard's exception. Either way, the design must say how step 1 reaches the set-aside file.

### [FAIL] The walkthrough's lost-state recovery does not match the start sequence

The walkthrough says that when the state directory is lost, "the start refuses and names the problem." D5 (line 249) and step 5 of the start sequence (line 453) refuse only a half pair of key and certificate. A wholly empty state directory passes: the hub makes a new certificate and step 7 creates an empty store. Every machine then gets `HubCertificateError` (line 255), and the error sends the operator to re-invite, which builds a new empty hub while the backups in `backup_dir` go unused. So "Dead ends found: none" (line 692) is wrong. Either refuse when the state directory is empty and `backup_dir` holds a backup, naming it, or correct the walkthrough and state this behavior in D14. A silent empty start is the fallback the principles forbid.

### [CONCERN] The kill-between-commit-and-reply criterion is tested as a dropped reply

The plan's criterion (slice plan 260, line 47) names a hub "killed between the commit and the reply." D18 tests a dropped reply with a stopped and restarted in-process server, and the departures table (line 541) records the substitution. The fixture already starts and kills a real `amoeba hub serve` subprocess (line 506), so the real case is available. The test does not need a hook in the child: send a `standing` call, poll `call_results` from a read-only connection for the row, then kill the child. Either outcome is valid (the repeat returns the first result, and the change applies once), so the test is not flaky. Keep the in-process hook for the reply-drop case.

### [CONCERN] Hub logging to stderr is not covered by D16's guarantee

D16 keeps refused calls off stdout and stderr so a scanner cannot fill the container's log. But D14 (line 461) turns off only the access log. The server libraries report other inbound failures on their own: a plaintext request or broken handshake on the TLS port, and a malformed HTTP request. By default, uvicorn and asyncio write those to stderr. The design should name the loggers those messages go to, route them to the hub log or drop them, and test that a flood of garbage bytes leaves stderr empty.

### [CONCERN] The hub's inbound path has no timeouts or connection limit

D6 refuses a body with no valid length before reading it, which bounds size. Nothing bounds time: there is no read timeout for headers or body, and no cap on open connections. A peer that opens connections and sends slowly holds them until the process runs out of sockets. The client side has handling for hang, refusal and non-reply. The hub side has none for a stalled or slow peer. Add a named read timeout in `wire.times`, state what happens when it fires (close, log, no store touch), and either cap connections or say why no cap is needed.

### [NOTE] The owner is on 12 tables, but the architecture's Owner section lists 8

The design puts `owner_id` on twelve tables, including `dependency_pairs`, `releases`, `deliveries` and `message_rejections`. The architecture's Owner section lists eight without those four. Its description (line 13) and the slice plan (line 37) both say "every record," so the design follows them. The departures table does not record the difference. Add a row for it, and the PM should reconcile the architecture's list in its next revision.

### [NOTE] Two plan departures are missing from the departures table

The departures table compares the design only with the architecture. Two rows also depart from the plan's wording. The plan says the migration gives the local store its machine (plan line 37), but this design creates it in the opener (line 408). The plan says kept results are "deleted by the sweep" (plan line 39), but line 351 deletes them at each call scope. The reasons hold: the message sweep is called only from the pause handler, `status` and `report_release`, and none of those is served here. Record both as plan departures so the 261 and 262 implementers do not read the plan wording as current.

### [NOTE] Scope the plan assigns to later slices is not named

The exclusions list says "the operations that name the caller (261)" but does not name the operations. The plan's 261 list is `inbox`, `reply`, `cancel`, `changes`, `report_release`, `add`, `rm`, `list`, `status`, and `send` for a recipient with no wake. 262 takes `answer` and `send` with waking. Name each excluded operation with its slice, so the served list can be checked against the plan. The same applies to `rm-machine` (line 428), which is the plan's first cut. Its checkouts (261) and questions, answers and wakes (262) are added later, and the design should say so, since the 260 transaction is what those slices extend.

### [NOTE] The client file's placement does not follow the test the design applies to the certificate

D1 keeps `client.yaml` in the config directory, as the architecture says, and moves the saved certificate to state because "`join` writes it and nobody edits it." `join` also writes `client.yaml`, and only `join --address` changes it. By the same reasoning it would be state. Either state that it stays in config because the architecture fixes it there and a person may edit it, or mark it as a parent-directed exception.

### [NOTE] Some parts could be cut without losing a requirement

Most of the design is required by the architecture or the plan: the owner triggers, the call scope, backups, the log and the fixture. Three small items can go. (1) The `via` paragraph (line 264) describes 262's behavior and is not built here. (2) The `wire.fingerprint` module (line 91) is about twenty lines and fits in `join_line`. (3) The `DoorTimes` parameter (line 311) threads through every call path so tests can shorten the times. Tests can patch the constants instead. Cutting (1) and (2) is clear. Cutting (3) is a judgment call.

### [PASS] The served list and the mode switch match the plan and the architecture

The six served operations match the plan's 260 list. The D2 table keeps the architecture's rule: the mode is decided on every call, and with a client file no local store is opened or created. Both entry points the architecture names are handled, and unserved operations fail with the plan's "the door does not serve it yet."

### [PASS] The trust model matches the architecture

Every call trusts only the saved certificate, does not check host names, and fails the handshake before any request byte is sent, as the architecture requires (arch line 117). The join fetch is the one exception with verification off, and it sends no token (line 210). The architecture's own join description (arch line 117) fetches the certificate and then checks it, so the exception matches the parent.

### [PASS] NFRs are restated with targets, and the claims about existing code hold

The load bounds are restated with targets: 2 seconds per call and a median under 200 ms, against the architecture's "a bound on call time." The dependency claims hold: the lock file lists `cryptography`, `starlette` and `uvicorn`, and `OPERATIONAL_ERRORS` is exported from `amoeba.wiring`. `decisions` and `standing` are the only served operations that call `cf`, as D11 assumes. The writing operations define an `unchanged` outcome, and `withdraw`'s docstring describes a compare-and-set repeat that answers it. I did not read the code of `mark_read` or `retract`, so their compare-and-set behavior is unverified.

### Run Digest

- Response length: 12562 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 15
- Tokens — prompt / cached / cache write / completion / reasoning: 1323056 / 1135353 / 187685 / 92350 / not computed
- Duration: 415.7 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

Resolved 20261120 in `user/slices/260-slice.hub-and-door.md`. Nothing was deferred and no issue was filed.

- [fail] The live-store migration is deferred to the release, against the plan: changed, by the PM's ruling that the live update is the last step of a release and never per merge. The plan's criterion is reworded by the PM's side, not the design. D19 now states what `scripts/update_live.py` does to the live store as the script is today: the backup it takes first and where it goes, the read-back, the restore by itself, the one backup kept, and the restore command. The departures row now cites the plan's Planning Context line.
- [fail] `amoeba leave` cannot restore a set-aside store as its steps are ordered: changed. The order stays, because it keeps the restored store closed until the client file is gone. D4 now says how step 1 reaches the file: `store.relocate` opens the set-aside file by its own path on a plain SQLite connection, not through either guarded opener, and a stop between clearing the mark and the rename is finished by the next run. The criterion asserts the restored store takes a write.
- [fail] The walkthrough's lost-state recovery does not match the start sequence: changed. An empty state directory beside a `backup_dir` that holds a backup is now refused, naming the newest backup and the `--from-backup` command; a new hub on purpose sets `backup_dir` to an empty directory. A store with no certificate is refused with the half pair. D5, start step 5, the departures table, two criteria and three walkthrough entries are updated.
- [concern] The kill-between-commit-and-reply criterion is tested as a dropped reply: changed. D18 adds a kill test on the fixture: the hub process is killed with `SIGKILL` once the kept result is on disk, and a repeat under the same id returns the first result. The dropped-reply test stays for the exact moment. The criterion and the departures row name both.
- [concern] Hub logging to stderr is not covered by D16's guarantee: changed. The handler is on the root logger and `uvicorn` runs with `log_config=None`, so `uvicorn.error` and `asyncio` lines land in the rotating hub log. A test floods the hub with garbage and asserts stderr holds only the serving line. D14, D16, a criterion and the walkthrough are updated.
- [concern] The hub's inbound path has no timeouts or connection limit: changed in part. No timeout or cap is added. Checked against the installed `uvicorn` 0.54: it has no first-request timeout, and `limit_concurrency` answers 503 to every caller once stalled connections reach it, which is worse. D14 now states what bounds a stalled peer (one socket, no thread, no store connection), the limit (the open-file limit), what happens when it is hit, and the way out (restart the hub). An idle timeout would mean replacing the server's protocol class, for a peer not expected on a LAN.
- [note] The owner is on 12 tables, but the architecture's Owner section lists 8: changed. A departures row records it.
- [note] Two plan departures are missing from the departures table: no change. Both rows are already in the table ("Kept results are deleted by the sweep" and "The migration gives the local store its one machine").
- [note] Scope the plan assigns to later slices is not named: changed. The exclusions name each operation with its slice, and what 261 and 262 add to `rm-machine`'s transaction.
- [note] The client file's placement does not follow the test the design applies to the certificate: changed. D1 says why `client.yaml` stays config.
- [note] Some parts could be cut without losing a requirement: no change. 262 cites the `via` paragraph (260 D6) and 262 and 263 pass their own times through `DoorTimes`; where the twenty lines of fingerprint code sit is the implementer's choice between two equal layouts.
- [pass] The served list and the mode switch match the plan and the architecture: no change.
- [pass] The trust model matches the architecture: no change.
- [pass] NFRs are restated with targets, and the claims about existing code hold: no change.

Also changed in this revision, outside the findings:

- 263's amendments to 260 are applied (D2, D6, D7, D8, D13), as forward statements of what 263 changes.
- `amoeba hub machines` no longer claims to show which machines are behind. This slice stores no door version for a machine, so it could not; 263 adds the column and the display (263 D6), which is where the architecture puts it.

## Full-text review, 20261121

A second review, run outside the pipeline after the task review kept finding new defects. The reviewer read the whole design (739 lines), the architecture, the slice plan and CLAUDE.md, checked the design's claims about existing code against the source, and tested the SQLite sequences in a scratch database. It did not see the review above. It found 4 important defects, 13 minor ones and 1 it could not confirm. All 18 are resolved in `user/slices/260-slice.hub-and-door.md` and carried into `user/tasks/260-tasks.hub-and-door.md`. Nothing was deferred and no issue was filed.

Important:

- Setting a store aside checkpointed inside its own write transaction, which SQLite refuses, and then removed the side files, losing committed rows when another command was reading: changed. The store is marked, copied with SQLite's backup call, and the original deleted. D4 has a table of every stop point and what `join` and `leave` do from it. Confirmed in a scratch database.
- A hub with a certificate and key and no store was in no row of the start rules and would have started empty: changed. D5 is now a table with a row for every combination, decided by whether a backup exists.
- An admin command run before the first `hub serve` created a store that the start then refused for good: changed. `open_hub_store` never creates a store; only step 7 of a first start does (D12, D13).
- A first start killed between its key and certificate, and a `--from-backup` killed partway, each left a state every later start refused: changed. The first is finished by the next start (D5). The restore is marked by `restore.partial/`, moves what it replaces into `replaced-<UTC stamp>/`, and is finished by the same command (D14).

Minor:

- `hello` had no stated place in the served check, no body and no result shape: changed (D6).
- `join` and `leave` had no stated error type or exit code for four refusals: changed. All are `JoinError`, exit 3 (D4).
- Two processes could take backups at once and delete each other's partial directory: changed. One file lock (D15).
- Nothing stopped `join --set-aside-local` or an ordinary command in the hub's own home: changed. Both are refused in a home that holds `hub.yaml` (D1, D2, D4).
- "Each of the twelve insert statements" was a wrong count (sixteen): changed, with a test that reads the statements (D12).
- "`unchanged` means it was applied" is not what the operations say: changed (D10).
- The departures table had no row for renaming the set-aside store: changed, with rows for `--from-backup` and the store-creation rule too.
- "The state directory is empty" was undefined: changed. Only the store, certificate and key count (D5).
- The fixture's seeding did not say which machine it acts as: changed (D12, D18).
- A migration failing at every restart rotated out earlier versions' pre-migration backups: changed. One backup per schema version (D15).
- The hub had no stated source for "today's operational errors": changed. `operations/errors.py`, as the task file already had it (D8).
- `join --set-aside-local` on a store below schema 11 hit a missing table: changed. The store is opened, and so migrated, first (D4).
- How `--from-backup` is run in the container was not stated, and a flag left in the compose file looped: changed (D14, D17).
- (unconfirmed by the reviewer) The per-call store open might be a second lock wait: checked. It is not; an open under a held write lock returned at once. D7 says so and a test pins it.

Also changed while fixing these: a store whose certificate is lost with no backup anywhere had no way on but deleting files. The hub now keeps the store, makes a new certificate and says every machine must join again (D5).
