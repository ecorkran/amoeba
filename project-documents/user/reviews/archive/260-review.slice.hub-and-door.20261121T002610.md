---
docType: review
layer: project
reviewType: slice
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/260-slice.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: bc6a352245d39a7b0f62b0512a6a41c5c8444413
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 1363794
cachedTokens: 1140953
cacheWriteTokens: 222823
completionTokens: 100705
durationSeconds: 459.0
costUsd: 0.516418
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: design-rules
    summary: "Saved hub certificate is system state kept under the client config directory"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:140-141"
  - id: F002
    severity: concern
    category: boundaries
    summary: "The served check does not come first at three entry points, so the no-file test would fail"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:146-166"
  - id: F003
    severity: concern
    category: architecture
    summary: "Client-side `cf` lookups for other members break the architecture's rule, and a client `cf` failure is reported as a hub error"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:325-328"
  - id: F004
    severity: concern
    category: testability
    summary: "The fixture cannot produce the decisions records that the criteria and load test need"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:437-438"
  - id: F005
    severity: concern
    category: error-handling
    summary: "A timed-backup failure at start stops the hub, against \"Always there\""
    location: "project-documents/user/slices/260-slice.hub-and-door.md:386-395"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Failure modes for the join certificate fetch and for a half-joined client are not stated"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:189-193"
  - id: F007
    severity: concern
    category: consistency
    summary: "Four departures from the architecture and the plan are not in the departures table"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:339-352"
  - id: F008
    severity: concern
    category: data-model
    summary: "\"An owner on every record\" is not met for four record tables"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:341-342"
  - id: F009
    severity: concern
    category: nfr
    summary: "One healthy call can use up the read time, and the touch is a separate transaction"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:267-269"
  - id: F010
    severity: concern
    category: boundaries
    summary: "Component table and import rules do not match what the design requires"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:90-104"
  - id: F011
    severity: concern
    category: error-handling
    summary: "Set-aside stores have no named cleanup and no stated bound"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:197-201"
  - id: F012
    severity: concern
    category: documentation
    summary: "The container has no config example, and two contracts changed here are deferred"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:443-448"
  - id: F013
    severity: concern
    category: walkthrough
    summary: "The operator walkthrough says \"Dead ends found: none\"; it does have dead ends"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:707"
  - id: F014
    severity: concern
    category: proportionality
    summary: "Proportionality: the verification walkthrough restates the criteria and the operator walkthrough"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:545-646"
  - id: F015
    severity: note
    category: nfr
    summary: "The latency requirement is not restated with a target"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:536"
  - id: F016
    severity: pass
    category: architecture
    summary: "Trust model matches the architecture"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:205-221"
  - id: F017
    severity: pass
    category: scope
    summary: "Scope matches the slice plan entry for 260"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:61-66"
---

# Review: slice — slice 260

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Saved hub certificate is system state kept under the client config directory

`pinned-hub-cert.pem` is placed in the client config directory (D1). `join` writes it, `leave` removes it, and no person edits it. It is a cached trust pin. The Amoeba rule "Config is config; state is state" says caches and anything the system writes belong in the state directory, and that state never lives under `~/.config`. The architecture asks for the file beside `client.yaml` (architecture line 140), but the rule is stated without exception and was added before that revision. Fix: move the pin to the client state home. That touches D1, the State table row at line 128, the closing note at line 131, D4, and the check at line 606. `client.yaml` can stay in config, since `join --address` edits it. If the PM wants the architecture's placement, the rule needs an explicit exception first.

### [CONCERN] The served check does not come first at three entry points, so the no-file test would fail

D2 says that with a client file the first thing every entry point does is the served check, and a test asserts that no file is created. The check is specified only in `wiring.invoke`, and three entry points do work before reaching it:
- `handle-pause` loads the config first, so a joined home fails with a missing-config error, not `NotServedError`. On error it writes a calls-log line, and line 157 says it still does. The no-file test cannot pass for it as written.
- `amoeba-mcp` start calls `prepare_home` and loads the config before serving. `prepare_home` raises the store-closed error, so start refuses with that error, not the `NotServedError` promised at line 158.
- `hub serve` copies backup files (step 2) and makes the certificate and key (step 3) before step 4 reaches the guard (lines 386-393). In a joined home it writes both files and then refuses.
Fix: put the served check, or for hub commands the guard, on the first line of each entry point, before any config read, state move or file write. Either place the calls-log write after the check or exclude `handle-pause` from the test by name.

### [CONCERN] Client-side `cf` lookups for other members break the architecture's rule, and a client `cf` failure is reported as a hub error

Architecture line 48 says "A client asks cf only about its own directory. Every other member is found in the store." D11 has the client send the whole id-to-name map for `decisions`, and resolve any `member` string in `standing` through its `cf`. The departures row at line 464 records the scope change but not that it breaks this principle. The design rules rule out deferring `standing --member`, so the PM has to accept or reject this exception explicitly, and the architecture should carry it. Also, `decisions` raises `ContextForgeError` when a listed member has no name. On the hub that error is reported as `hub_error`, so a failure on the client's machine looks like a hub failure. The reply shape for a client `cf` failure with records present is not specified.

### [CONCERN] The fixture cannot produce the decisions records that the criteria and load test need

The load test reads `decisions` over a seeded store of 500 answers (line 438), and the criterion at lines 516-517 needs records shown. Under D11, records need member names from the client's `cf`, and `decisions` raises when a listed member has no name. The design does not say how the fixture client homes get names for seeded members, or inject a name reader. Unless the design adds that, the read half of the load test fails with `hub_error`.

### [CONCERN] A timed-backup failure at start stops the hub, against "Always there"

D14 says any failure during start stops the hub, and step 5 takes a timed backup at start. So an unwritable backup disk on restart stops the hub, and `restart: always` loops. D14's own periodic task (line 395) and the walkthrough's "Backups stop working" case (line 701) assume the hub keeps running after a backup fails. The architecture requires the hub to start at boot, restart on failure and back itself up (architecture line 36). Fix: a failed timed backup at start logs at error level and the start continues. Only the pre-migration backup (line 411) should stop the start. Otherwise record the choice as a departure and state its cost.

### [CONCERN] Failure modes for the join certificate fetch and for a half-joined client are not stated

Join step 3 fetches the certificate from the handshake (also D5, line 218). D4 covers only a fingerprint mismatch. Refused connections, timeouts, a peer that accepts TCP but does not speak TLS, and a hang are not stated, and the fetch has no timeout in the design. `joined()` loads only `client.yaml`, so a missing or unreadable pinned certificate has no specified error. Fix: give the fetch a connect time and list each failure with its error and whether it is retried. Name the error for a missing pin, as D3 does for a bad key.

### [CONCERN] Four departures from the architecture and the plan are not in the departures table

1. The `local` machine is created on first insert, not by the migration. The plan (line 37) says the migration gives the local store its machine. D12 gives a reason (a fresh hub must not get `local`), which is sound, but it is not recorded.
2. The migration inserts the owner row. The architecture (line 211) says the hub creates the owner when it first starts.
3. The join line includes the machine name (line 175). The architecture (line 138) lists the address, fingerprint and token.
4. `machines.owner_id` (line 340) has no null trigger and no insertion rule. Admin `invite` has no acting machine, so how it sets the owner is not stated.
Fix: add rows for 1 to 3, and specify 4.

### [CONCERN] "An owner on every record" is not met for four record tables

The architecture says "An owner on every record" (line 66) and its description says "every record names its owner" (frontmatter, line 13). The design adds `owner_id` to the eight tables from the architecture's Owner section (line 211). The schema also has `releases` and `dependency_pairs` (baseline) and `deliveries` and `message_rejections` (migration 006), all written by insert. The design should add them with the same trigger, or state why they are not records.

### [CONCERN] One healthy call can use up the read time, and the touch is a separate transaction

D7 says the hub's own store wait is the 5-second busy time, so 10 seconds to read "always covers a hub that is going to answer." D8 makes more than one lock wait per call: the touch (step 2, line 281) commits by itself, and the call scope takes `BEGIN IMMEDIATE` (step 5). Each can wait up to the busy time, so a call can spend two busy times before the operation runs. The pinned test (line 269) checks only that `READ_SECONDS` is above one busy time. The separate touch transaction also departs from "One hub call is one whole transaction" (architecture line 59), and that departure is not recorded. Fix: fold the touch into the call scope, committing on the refusal path too. Pin `READ_SECONDS` above the total waits per call.

### [CONCERN] Component table and import rules do not match what the design requires

1. The `hub` import rule is checked on direct imports. `hub` reaches the store through `wiring.open_store`, and `wiring` imports the Context Forge and Squadron packages and the client file reader. So `hub` reaches `cf`, Squadron and `client` through `wiring`, which contradicts "The hub has no cf and no Squadron" (architecture line 90). The tests would still pass. Fix: put the store opener and the guard in a module below `wiring` that `hub` can import.
2. The set-aside step in `join` takes the store's write lock and renames the store (line 197). `client` may not import `store` (line 103), so `client.join` cannot do it. Name the module that owns it.
3. The table omits the changes D2 requires: the `amoeba-mcp` server's start and tool path, and the CLI's `handle-pause` and `wake-run` commands.

### [CONCERN] Set-aside stores have no named cleanup and no stated bound

Each `join --set-aside-local` leaves a full copy of the store. `leave` restores only the newest, and D4 says older ones stay as "one file per set-aside, path printed." That is neither a named cleanup nor a bound. The design already rejects a joined state with no command, for the same reason (line 203). Fix: name a cleanup, for example `leave` lists the set-asides and removes one by its stamp, or state the bound and why it holds.

### [CONCERN] The container has no config example, and two contracts changed here are deferred

1. The architecture (line 84) says the image ships the `config.yaml` example, as it ships `hub.yaml`. D17 ships only `hub.yaml.example`. Verification step 9 relies on copying `config.yaml` from `docs/config-contract.md` (line 566), which the container does not contain.
2. D19 says "this slice documents its own additions" (line 443). But this slice changes `amoeba-mcp` start and tool behavior and makes `handle-pause` and `wake-run` refuse. The architecture lists `docs/mcp-server.md` and `docs/squadron-hook.md` as changed (line 316). The plan defers both to 264 (plan line 151), which conflicts with D19's own rule.
Fix: ship a `config.yaml` example in the image, and document both contracts in this slice.

### [CONCERN] The operator walkthrough says "Dead ends found: none"; it does have dead ends

Walking the design as the operator, I found:
- In the container, no `config.yaml` example is available (see the documentation finding).
- `decisions` with records and no usable `cf` on the client returns an error, not a list. The walkthrough at line 547 says `cf` is not needed, but the gather step calls it.
- The `bad_token` refusal is to show "the commands to come back" (line 699). D6 does not define the refusal text, so those commands are not guaranteed to appear.
- A `hub serve` on a taken port migrates the store and takes a pre-migration backup before the bind fails (step 4 before step 6). A start that cannot serve should fail before it migrates.

### [CONCERN] Proportionality: the verification walkthrough restates the criteria and the operator walkthrough

The 100-line verification walkthrough repeats the functional criteria (lines 513-530) as shell steps, and the operator walkthrough (lines 686-707) covers the same ground. Cut the shell walkthrough to a pointer from each criterion to its fixture test, and keep the operator walkthrough. The D5 evidence narrative (lines 214-219) can shrink to one line that names the pinned test. The Prerequisites version numbers (lines 73-74) restate `uv.lock` and can point to it.

### [NOTE] The latency requirement is not restated with a target

The architecture states "A CLI call is a `cf` call plus one round trip" (line 287). The design states a 2-second bound only for the load test. Stating a call-time target for an unloaded hub would make the requirement checkable. Not blocking.

### [PASS] Trust model matches the architecture

The pinned certificate is checked during the handshake, host names are not checked, no system roots are loaded, and a hub with the wrong certificate never receives a request (criterion at line 518). Tokens are stored as SHA-256 hashes, the key and client file are mode 0600, and a half certificate pair stops the hub. This matches architecture lines 117-118 and 285.

### [PASS] Scope matches the slice plan entry for 260

The six served operations, the admin commands, backups, the log, the container, the fixture and the load test are all in scope, and the exclusions for 261 to 264 are listed. The one plan deviation, the `local` machine, is recorded above.

### Run Digest

- Response length: 15988 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 1363794 / 1140953 / 222823 / 100705 / not computed
- Duration: 459.0 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
