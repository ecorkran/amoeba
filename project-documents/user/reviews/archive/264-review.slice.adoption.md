---
docType: review
layer: project
reviewType: slice
slice: adoption
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/264-slice.adoption.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: e288ddea94f189557344b590fc58fdee06a417de
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: xhigh
turns: 11
promptTokens: 761873
cachedTokens: 562744
cacheWriteTokens: 199117
completionTokens: 116069
durationSeconds: 520.8
costUsd: 0.504648
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: state-lifecycle
    summary: "Three states end only when someone edits files"
    location: "project-documents/user/slices/264-slice.adoption.md:132-142"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "Four parent items are reversed inside the design"
    location: "project-documents/user/slices/264-slice.adoption.md:406-425"
  - id: F003
    severity: concern
    category: data-integrity
    summary: "A release before 260 can write to the handed-over store, and the write is lost silently"
    location: "project-documents/user/slices/264-slice.adoption.md:194-199"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "A second load discards call results kept on the hub"
    location: "project-documents/user/slices/264-slice.adoption.md:170"
  - id: F005
    severity: concern
    category: security
    summary: "Admin writes during the load window can be undone, including a token revocation"
    location: "project-documents/user/slices/264-slice.adoption.md:254-256"
  - id: F006
    severity: concern
    category: under-specification
    summary: "The two lists of hub tables disagree, and one is self-contradictory"
    location: "project-documents/user/slices/264-slice.adoption.md:214"
  - id: F007
    severity: concern
    category: under-specification
    summary: "The adoption decision table has overlapping rows"
    location: "project-documents/user/slices/264-slice.adoption.md:155-157"
  - id: F008
    severity: concern
    category: dependency-direction
    summary: "The import rules contradict each other, and `join` breaks one of them"
    location: "project-documents/user/slices/264-slice.adoption.md:109-111"
  - id: F009
    severity: concern
    category: failure-modes
    summary: "Failure modes are missing for three paths"
    location: "project-documents/user/slices/264-slice.adoption.md:218-231"
  - id: F010
    severity: concern
    category: under-specification
    summary: "Old state under `~/.config` is assumed away"
    location: "project-documents/user/slices/264-slice.adoption.md:302"
  - id: F011
    severity: concern
    category: under-specification
    summary: "Parent facts are restated differently or left unstated"
    location: "project-documents/user/slices/264-slice.adoption.md:140"
  - id: F012
    severity: concern
    category: proportionality
    summary: "Proportionality: two additions are heavier than the requirement"
    location: "project-documents/user/slices/264-slice.adoption.md:362"
  - id: F013
    severity: concern
    category: operator-walkthrough
    summary: "The operator walkthrough misses dead ends"
    location: "project-documents/user/slices/264-slice.adoption.md:603"
  - id: F014
    severity: note
    category: completeness
    summary: "The verification walkthrough is still a draft"
    location: "project-documents/user/slices/264-slice.adoption.md:516"
  - id: F015
    severity: note
    category: process-sequencing
    summary: "The live install is sequenced before code review and merge"
    location: "project-documents/user/slices/264-slice.adoption.md:395-404"
  - id: F016
    severity: pass
    category: scope
    summary: "Deletions and their consumers are listed"
    location: "project-documents/user/slices/264-slice.adoption.md:289-304"
  - id: F017
    severity: pass
    category: data-integrity
    summary: "The schema premise holds in the current code"
    location: "project-documents/user/slices/264-slice.adoption.md:194"
  - id: F018
    severity: pass
    category: nfr
    summary: "Hub-side upload failures and load bounds are stated"
    location: "project-documents/user/slices/264-slice.adoption.md:218-231"
  - id: F019
    severity: pass
    category: interfaces
    summary: "Interfaces cited from 262 and 263 match those slices"
    location: "project-documents/user/slices/264-slice.adoption.md:79-83"
---

# Review: slice — slice 264

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Three states end only when someone edits files

The Amoeba design rule requires every state to end "with nobody editing files." Three states do not:
- **The handed-over store** (line 135) stays at the store path. Its only exit, `adopt --again`, re-enters the flow rather than ending the state. The walkthrough says it stays "until the PM deletes them" (line 601).
- **The records a failed hub update keeps** (line 362) come back only when the PM copies three files by hand and starts a fixed release.
- **The pre-handover backups** (line 136) have no cleanup. "One per handover" bounds them only as far as `--again` is not run again, and each run adds a full copy.

Name a command that ends each state, such as one that removes a handed-over store and its backups after the hub confirms it holds the adoption. For the failed-update records, name the command that puts them back.

### [CONCERN] Four parent items are reversed inside the design

The departures table reverses four things the parents require:
- the refusal while a local session is live (slice plan 264 criterion; architecture, adoption step 1);
- the refusal when a member is unnamed (architecture, step 1);
- the rename of the store to a dated backup (architecture, step 6);
- "only the hub opens the store" (architecture principle; plan criterion "no code opens a store outside the hub and its admin commands").

Each has a stated reason. But the architecture amendment is the last task (line 393), the slice plan is not listed for amendment, and tasks 1 to 7 would be built against a principle the parent still states. The PM should decide each departure, and the architecture and slice plan should be amended before the first task that opens a store. The live-session refusal matters most, because the replacement guard depends on the claim in the next finding.

### [CONCERN] A release before 260 can write to the handed-over store, and the write is lost silently

Line 199 accepts this case: a release before 260 has no mark check, so its write "succeeds with no error, into a store nothing reads, and is not on the hub." The window is short, but the write is lost with no message, and the design names only `handle-pause` as a writer that matters. The walkthrough does not walk this case. The no-silent-fallback rule needs either a signal the PM can see (for example, counts recorded at handover and compared by `list`, `join` or `adopt --again`), or an accepted-risk statement that is walked through.

### [CONCERN] A second load discards call results kept on the hub

When the hub holds this adoption and its own digest has not moved, "load again" replaces the whole store with the laptop's copy (step 5, line 247). Step 3 carries over only machines. The hub's kept call results go (line 174 says the load rewrites them), and so do session and run rows. A writing call whose reply was lost, retried within the retry window after the load, would apply a second time. That breaks the architecture's "a lost reply never applies twice," and the departures table (line 419) lists only the three adoption calls as keeping no result. Carry `call_results` across the load, or list the departure and walk the case.

### [CONCERN] Admin writes during the load window can be undone, including a token revocation

The gate is a flag in the serving process. Step 2 reads the machines, step 3 writes them back, and step 5 replaces the store. An admin command runs in another process, so one that commits between steps 2 and 5 is lost. Line 256 names only a lost invite. The same window undoes a `hub rm-machine` and a re-invite: the removed machine's row, or the old token's hash, is written back from the step-2 read, so a revoked token works again. The slice plan's 260 criteria require a removed or re-invited token to end "at once." Hold the store's write lock from the step-2 read through the copy, or have admin commands check a store-level marker set at step 2. Add an admin write inside the window to the test described at line 254.

### [CONCERN] The two lists of hub tables disagree, and one is self-contradictory

The digest excludes `machines`, `sessions`, `machine_runs`, `call_results`, `closed_mark` and `adoption` (line 174). The emptiness check skips `schema_meta`, `owners`, `machines`, `pm_marker`, `call_results`, `machine_runs`, `closed_mark` and `adoption` (line 214). They disagree about `sessions`, which is excluded from the digest but checked for emptiness, and about `schema_meta`, `owners` and `pm_marker`, which are digested but skipped for emptiness. Line 214 also calls the list tables the hub "fills by itself," then requires `adoption` to hold no row. As written, a second joined machine's live session row blocks adoption as `hub_not_empty`, and the walkthrough does not mention it. Define one table list with a reason for each entry, and derive both checks from it.

### [CONCERN] The adoption decision table has overlapping rows

A store from `join --set-aside-local` has a mark for hub H and no adoption id. If a client file for H also exists, it matches both "a mark for this line's hub, and a client file" (line 156), which finishes step 8 and prints the result, and "a mark and no adoption id" (line 157), which rejects. The first row would rename `config.yaml` and report an adoption for a store that was never loaded. Give the table an order with the no-adoption-id test first, and add this case to the adoption tests.

### [CONCERN] The import rules contradict each other, and `join` breaks one of them

Line 109 says the `wiring` modules other than `wiring_adopt` import nothing from `amoeba.store` but its error types. Line 111 lets `wiring_door`, one of those modules, import `amoeba.store.handover`. Also, `join --set-aside-local` opens the store through `handover` (line 271), but the component table puts `join_command` in `amoeba.cli` (line 101), which neither rule allows. The import test cannot pass as written. Name the one module that calls `handover` for each command, and state the rule once.

### [CONCERN] Failure modes are missing for three paths

The hub side of the upload is enumerated well. These are not:
- **Client, peer closes mid-send.** The concurrent-upload refusal (line 225) does not say whether the hub reads the body first. If it does not, a client still sending a 160 KB body sees a connection reset and never sees the refusal. Line 231 covers only "no reply." State what the client reports.
- **Retry after a successful load.** The step-2 check (line 241) would skip the load, but the upload route's answer is not stated.
- **`hub_update_command` (line 344)** has no time bound. A hung `ssh` stalls `update_live.py`. The 300-second bound (line 345) covers only the polling in step 4.
- **`hub-restore.sh` (line 362)** has no failure handling of its own. If it stops halfway, the state it leaves is not stated.

### [CONCERN] Old state under `~/.config` is assumed away

The design deletes the pre-228 move and says a machine still holding state from before 228 "would get the join message with no mention of its old state," on the assumption that no other install is that old. I checked the PM's laptop: `~/.config/amoeba` holds only `config.yaml`, as line 302 says. The other machines the PM works on are not checked. A machine with old state would lose it without a word. Check those machines, or add a file-exists test for the old store path in `join` and `adopt` that names the file. That is one check, and it removes the silent case.

### [CONCERN] Parent facts are restated differently or left unstated

- **Saved certificate.** The state table puts it in the "client state directory" (line 140). The architecture puts it in the config directory beside the client file. The departures table does not list this change.
- **Door version.** Line 98 adds `ADOPT_READ_SECONDS` and `UPLOAD_IDLE_SECONDS` to `wire.times`, and line 216 adds refusal codes. The architecture says a change to a shared network time changes the door version. State whether this release bumps `DOOR_VERSION`, and why.
- **Clock.** `sessions_to_restart` (line 197) uses a fresh-heartbeat test on the laptop's copy, so the laptop's clock decides. The architecture says stale rows are judged on the hub's clock. Compute the list from the hub after the load.
- **Copy connection.** Step 5 (line 121) does not say which connection makes the SQLite backup copy while the lock is held. SQLite's backup documentation says a writing source connection gets `SQLITE_LOCKED` from the step call, so the copy should come from a second connection. Verify that against the SQLite version in use, name the connection, and test it.
- **`add-config-keys`** (lines 366-368) appends missing keys to a YAML file but does not say how a nested required key is detected or where it is inserted. Appending a top-level key that already exists duplicates it. Specify both.

### [CONCERN] Proportionality: two additions are heavier than the requirement

The plan rates 264 at relative effort 3. The design adds more than the plan names: `hub-update.sh`, `hub-restore.sh`, `restore --hub`, a `live-update.yaml` with two commands, `add-config-keys`, and `--again`. Most of these follow from the undo and release requirements. Two are heavier than needed:
- **The `no_room` refusal code** and its free-space report (line 228). A `hub_error` that carries the OS message leaves the store untouched and is still explicit. Cut the new code.
- **The `replaced/` rotation** ("one is kept," line 362). Moving the three files into one timestamped directory that the script prints meets the requirement. The keep-one rule adds code and a test that no requirement asks for.

### [CONCERN] The operator walkthrough misses dead ends

The walkthrough says "Dead ends found: one." Walking the design as the operator found these as well:
- a write from a pre-260 connection after the switch (finding above);
- a `rm-machine` or re-invite during the load (finding above);
- a second machine's live session blocking adoption, with no step given; the exit is the session going stale and being pruned, which should be said;
- the `hub_update_command` hang (finding above);
- a `hub-restore.sh` failure partway through.

Add each one, with its exit, to the walkthrough.

### [NOTE] The verification walkthrough is still a draft

"Draft; refined after implementation." The commands and test names are already specific. Settle the names and the by-hand steps now, so the design can be checked against them before anything is built.

### [NOTE] The live install is sequenced before code review and merge

Line 404 says the install runs from the slice branch before the merge. The project's git rules put code review before the merge. That means the PM's live store would be migrated by code that has not passed review. A review fix to the migration or the load would mean restoring the store from its backup and running again. The backup and D11 make that recoverable. State the order in the design, and say which path a review fix takes.

### [PASS] Deletions and their consumers are listed

D7 names each deleted item and the consumers updated in the same task. This matches the plan's "Deleting" bullet, and each deletion keeps the suite passing.

### [PASS] The schema premise holds in the current code

D2 relies on older releases refusing a store with a newer schema. The current code does refuse a store newer than the version it expects. I did not verify the second premise in the same paragraph, that each older store use opens a new connection.

### [PASS] Hub-side upload failures and load bounds are stated

The hub side of the upload has a handling for each case: partial body, idle sender, full disk, hash mismatch and concurrent upload. The door's latency bounds from 260 (every call under 2 seconds with 16 clients, median under 200 ms on an idle hub) are restated at line 335. The client-side gap is covered in the failure-mode finding.

### [PASS] Interfaces cited from 262 and 263 match those slices

I checked the `open_state_store` fix for old question and wake rows (262 D14) and the `LIVE_SESSION` predicate with the session's door version (263 D13). The design uses both as those slices define them. I did not check the naming fix (261 D4).

### Run Digest

- Response length: 14516 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 761873 / 562744 / 199117 / 116069 / not computed
- Duration: 520.8 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19
