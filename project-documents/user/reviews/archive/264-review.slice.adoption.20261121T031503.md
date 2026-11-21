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
reviewedSha: e15e661629b8e9cf9ed80e85fc18764a2fa10fcb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: xhigh
turns: 11
promptTokens: 1243166
cachedTokens: 1014700
cacheWriteTokens: 228450
completionTokens: 111225
durationSeconds: 503.2
costUsd: 0.544483
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "`join --set-aside-local` migrates the live store with no backup"
    location: "project-documents/user/slices/264-slice.adoption.md:249"
  - id: F002
    severity: fail
    category: operator-walkthrough
    summary: "The walkthrough says \"no dead ends,\" but two of its ways on are dead ends"
    location: "project-documents/user/slices/264-slice.adoption.md:562"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A cut-off after the client file leaves a `config.yaml` nothing reads"
    location: "project-documents/user/slices/264-slice.adoption.md:124"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "\"Fail until restarted\" contradicts 263 and the design's own D6"
    location: "project-documents/user/slices/264-slice.adoption.md:188"
  - id: F005
    severity: concern
    category: error-handling
    summary: "The handover guarantee covers only 260-and-later writers; the pre-260 case is silent"
    location: "project-documents/user/slices/264-slice.adoption.md:190"
  - id: F006
    severity: concern
    category: data-integrity
    summary: "Equal row counts are taken as \"nothing changed,\" so in-place updates are missed"
    location: "project-documents/user/slices/264-slice.adoption.md:167"
  - id: F007
    severity: concern
    category: data-integrity
    summary: "The pre-adopt backup is a file copy, not SQLite's backup call"
    location: "project-documents/user/slices/264-slice.adoption.md:119"
  - id: F008
    severity: concern
    category: architecture-alignment
    summary: "Upload and load store work has no stated worker thread"
    location: "project-documents/user/slices/264-slice.adoption.md:218"
  - id: F009
    severity: concern
    category: error-handling
    summary: "The upload's hub-side failure modes are not enumerated"
    location: "project-documents/user/slices/264-slice.adoption.md:209"
  - id: F010
    severity: concern
    category: architecture-alignment
    summary: "The write lock is held across three network calls, against the parent's transaction rule"
    location: "project-documents/user/slices/264-slice.adoption.md:121"
  - id: F011
    severity: concern
    category: architecture-alignment
    summary: "Writing calls keep no result, against the parent's repeat rule"
    location: "project-documents/user/slices/264-slice.adoption.md:197"
  - id: F012
    severity: concern
    category: architecture-alignment
    summary: "`config.yaml.before-keys` adds a third file to the hub's config directory"
    location: "project-documents/user/slices/264-slice.adoption.md:140"
  - id: F013
    severity: concern
    category: data-integrity
    summary: "Automatic hub rollback can roll back a healthy hub's store"
    location: "project-documents/user/slices/264-slice.adoption.md:330"
  - id: F014
    severity: concern
    category: proportionality
    summary: "A second test transport and an estimated disk check, where lighter options exist"
    location: "project-documents/user/slices/264-slice.adoption.md:294"
  - id: F015
    severity: concern
    category: error-handling
    summary: "`hub add-config-keys` does not say where its example values come from"
    location: "project-documents/user/slices/264-slice.adoption.md:341"
  - id: F016
    severity: note
    category: docs
    summary: "\"A set-up page\" means two different things in the design"
    location: "project-documents/user/slices/264-slice.adoption.md:43"
  - id: F017
    severity: note
    category: docs
    summary: "The parent architecture needs the departures written into it"
    location: "project-documents/user/architecture/260-arch.the-hub.md:58"
  - id: F018
    severity: note
    category: scope
    summary: "The pre-228 case rests on an assumption that was not checked"
    location: "project-documents/user/slices/264-slice.adoption.md:280"
  - id: F019
    severity: pass
    category: architecture-alignment
    summary: "The adoption sequence follows the parent's steps and the plan"
    location: "project-documents/user/slices/264-slice.adoption.md:115"
  - id: F020
    severity: pass
    category: architecture-alignment
    summary: "Import rules and the client boundary match the parent"
    location: "project-documents/user/slices/264-slice.adoption.md:106"
---

# Review: slice — slice 264

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] `join --set-aside-local` migrates the live store with no backup

D5 says `join --set-aside-local` opens the store through `store.handover`, which runs migration 015 (line 289), and that it "takes no backup of its own." The Amoeba design rule on the PM's live store says a migration takes a backup first, with a stated restore path. 262 already does this for its migration (262 slice, line 499: "The script backs up first"). Adoption's step 3 backs up, but this path does not. Fix: take the same pre-migration backup inside `store.handover`, before the migration, and state its path.

### [FAIL] The walkthrough says "no dead ends," but two of its ways on are dead ends

Lines 547 and 551 send the PM to `join --set-aside-local` as the way on. That marks the laptop's store, and "nothing reads it" (line 250). Merging two stores is excluded (line 67), so the laptop's records reach a hub only through a fresh, empty hub, which drops the records on the hub being kept. Two more cases are not reported:
- "Start the hub on an empty state directory" (line 547) issues a new certificate. Every machine already joined then gets `HubCertificateError` and must be re-invited and re-joined (260 slice, lines 255 and 687). The walkthrough does not say so.
- A marked store whose hub answers `empty` or refuses the `holds_this` check has no stated outcome. Line 153 says the hub "must answer holds_this" and gives no failure.

Record each as a dead end with its exit, or change the way on.

### [CONCERN] A cut-off after the client file leaves a `config.yaml` nothing reads

Step 8 writes the client file before renaming `config.yaml` (line 124). A cut-off between the two leaves a live `config.yaml` beside a client file. The re-run row at line 154 says "Done... changes nothing," so the rename never happens. The departure row at line 390 renames the file for this reason: "an edit to a file nothing reads would fail without a word." The re-run should finish the rename.

### [CONCERN] "Fail until restarted" contradicts 263 and the design's own D6

D2 says each listed session's tools "fail with the schema error until it is restarted," and the walkthrough repeats it (line 546). 263 says a session open across a join "uses the hub from its next tick" (263 slice, line 551). D6 says a machine that joins later is "served from the session's next call, with no restart" (line 261). Sessions on 260–263 switch to the hub once the client file exists. Only sessions on releases before 260, which have no mode switch, need a restart. Restrict `sessions_to_restart` to those and say how they are identified. Correct line 546. Also add 263's `LIVE_SESSION`, which line 188 uses, to Interfaces Required (lines 77–83).

### [CONCERN] The handover guarantee covers only 260-and-later writers; the pre-260 case is silent

D2 says a connection opened before step 4 fails its next write "for releases from 260 on," because of the mark check. It then says "a release before 260 has no mark check" and stops. A pre-260 `handle-pause` settle would then write into the kept store with no error and nothing on the hub. The departure row at line 381 ("No program that can open the migrated store writes to it") rests on this guarantee. Name the outcome for this case, or narrow the departure's claim to 260-and-later releases.

### [CONCERN] Equal row counts are taken as "nothing changed," so in-place updates are missed

The re-run table skips the load when the laptop's counts equal the hub's loaded counts (line 167). A changed row with the same count, such as a recorded answer, a request marked read or an edited standing answer, is not detected, and the hub keeps the old state. The success criterion at line 450 tests only inserts. The parent uses counts (260-arch, line 238) but also keeps "the store's sequence numbers" (260-arch, line 64). Use a store change marker or a digest of the copy, and test an update as well as an insert.

### [CONCERN] The pre-adopt backup is a file copy, not SQLite's backup call

Step 3 says "copy the store and `config.yaml`." The parent requires backups "made with SQLite's own backup call" (260-arch, line 92), and step 5 uses that call. Unless the store is checkpointed and has no `-wal` file, a file copy misses committed rows. The restore path at line 355 copies this file back over the store path, so it may restore an incomplete store. Use the backup call for step 3 and name the file it writes.

### [CONCERN] Upload and load store work has no stated worker thread

The parent says each request "does its store work in a worker thread on its own connection, so no store call runs on the event loop" (260-arch, line 284), and the load test must show "no tick is starved" (line 286). D4 does the lock, the backup into the hub's store, the prepare step and the counts (lines 220–228). D3 hashes the body (line 209). None of this is said to run in a worker thread. The design says the load takes "well under a second" (line 234), which would stall every tick and call for that second. State the thread and add a test that a tick is not starved during an upload.

### [CONCERN] The upload's hub-side failure modes are not enumerated

The upload is a new I/O path. D3 gives the client's 120-second read time and the lost-reply outcome (line 211). D4 gives `copy_damaged` for a bad hash. Not stated: what the hub does when the body stops partway (peer disconnect mid-send), how long it waits for body bytes (hang), and whether a short body is refused as `copy_damaged` or as a transport error. "No fixed size limit" (line 209) is given without a hub-side read timeout. Enumerate each case and its handling.

### [CONCERN] The write lock is held across three network calls, against the parent's transaction rule

The parent says "No transaction spans two network calls" (260-arch, line 59). It also says the copy lock is held "until step 6" (line 237), so the parent contradicts itself. This design holds the lock from step 5 through the upload (step 6) and the config call (step 7) to the commit at step 8 (lines 121–124). That is up to the read time of each call plus retries, while local writers wait. State the maximum hold time, record the departure from the rule, and say what a waiting writer sees when the wait runs out.

### [CONCERN] Writing calls keep no result, against the parent's repeat rule

The parent requires every writing call to carry a client id and keep its result so a repeat returns it (260-arch, line 62). D3 says "None keeps a result" (line 197). `adopt_config` writes config, so a repeat after a lost reply returns `kept`, not `written` (line 203). The adopt result would then report `config: kept` for a file this call wrote (line 422). Keep the result for `adopt_config`, or record the departure in the table at lines 377–392, which does not list it.

### [CONCERN] `config.yaml.before-keys` adds a third file to the hub's config directory

The parent's container has "config: two files and nothing else" (260-arch, line 84). Line 140 adds `config.yaml.before-keys` to the hub's config directory, and line 341 writes it. The amendments table (lines 394–404) amends the mount to writable but not this rule. Keep the copy in the state directory, which the project rule requires for state, or amend the parent's container description and record it.

### [CONCERN] Automatic hub rollback can roll back a healthy hub's store

D10 runs `hub_restore_command` when step 3, 4 or 6 fails (line 330). Step 6 is a laptop-side read-back, and step 4 is a 300-second wait for `hello` (line 325). Either can fail while the hub is fine. `hub-restore.sh` then moves the live store aside and starts from a backup (line 337). The design says what was recorded after the update began "is lost," yet the same paragraph moves that store into `replaced/`, so the records may still exist, and the design does not say how to recover them. The parent's undo is manual: "the previous image with `serve --from-backup`" (260-arch, line 95). Roll the hub back only on a hub-side failure, name the recovery path for the moved records, and reduce the automatic path to the manual one the parent specifies.

### [CONCERN] A second test transport and an estimated disk check, where lighter options exist

- `DirectTransport`, the `Transport` protocol and `joined_home` (D9) add a second in-process hub. 260 already has one: uvicorn in a thread, with real TLS. The design lists it as an interface it consumes (line 79; 260 slice, lines 503–504). The design does not say why a fixture-scoped instance of that helper is too slow. Justify the seam with a timing figure, or reuse the helper.
- The `no_room` refusal (line 209) estimates free space at three times `Content-Length`. Catching the write's out-of-space error and refusing with the two figures meets the same requirement without an estimate.

The architecture slice plan rates 264 at effort 3 (`260-slices.the-hub.md`, line 169). The design is larger than that entry. Cut or simplify these two parts before implementation.

### [CONCERN] `hub add-config-keys` does not say where its example values come from

The command appends each missing key "with the value from the example in the shipped config contract." The design does not say which file it reads, how it finds the example for a key, or what happens when a key has none. 260 places the example in `/usr/share/amoeba/config-contract.md` (260 slice, line 644). Reading values from a markdown document is fragile. State the file, the format and the failure when an example is missing, and test against the shipped document itself.

### [NOTE] "A set-up page" means two different things in the design

The Overview says "the hub gets a set-up page" (line 43). D12 makes `docs/hub-setup.md`, a repository document (line 362). D10 rejects "restoring the hub by hand from the set-up page" (line 345). The architecture slice plan's wording is also ambiguous (`260-slices.the-hub.md`, line 151). Say which one it is.

### [NOTE] The parent architecture needs the departures written into it

This design departs from the parent's principles at lines 58 (only the hub opens the store), 59 (no transaction spans two network calls) and 62 (repeats), and from the adoption steps at lines 233–240 (refusal, rename, mark). The departure table in the slice covers them, but 265 and 300 will read the parent. Amend the parent in the same commit, or make the amendment an explicit task.

### [NOTE] The pre-228 case rests on an assumption that was not checked

Line 280 says "The only install that old was the PM's." The design checked only the PM's home, on 20261120. State that as an assumption, or check the other homes. A machine that still has pre-228 state gets "not joined" with no mention of its old state.

### [PASS] The adoption sequence follows the parent's steps and the plan

The data flow (lines 115–124) keeps the parent's order: a check before any write, an adoption id, a backup, the copy under lock, the load with counts, config, then the switch, with the mark written in the lock's transaction and the client file last. The upload is token-checked before the body is read and sent over the pinned connection, as the parent requires (260-arch, lines 117–118).

### [PASS] Import rules and the client boundary match the parent

Lines 108–111 keep `amoeba.mcp` and `amoeba.client` free of store imports except error types, restrict `Store.open` to two modules, and limit the handover code to the wiring that needs it. These follow "a client holds no store" (260-arch, line 37).

### Run Digest

- Response length: 14839 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1243166 / 1014700 / 228450 / 111225 / not computed
- Duration: 503.2 s
- Cost: $0.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20
