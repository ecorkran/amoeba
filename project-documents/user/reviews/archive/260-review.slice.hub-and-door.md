---
docType: review
layer: project
reviewType: slice
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/260-slice.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: c0771444bed3f306017b3cc96bee5ceeb3729c95
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 2030228
cachedTokens: 1807747
cacheWriteTokens: 222457
completionTokens: 106808
durationSeconds: 488.1
costUsd: 0.567137
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "A plan success criterion is deferred to 262 without a valid reason"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:495"
  - id: F002
    severity: concern
    category: security
    summary: "The join certificate fetch has no stated TLS setting and conflicts with the parent's connection rule"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:204"
  - id: F003
    severity: concern
    category: architecture
    summary: "The unknown-outcome rule departs from the parent without being listed"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:334"
  - id: F004
    severity: concern
    category: state-exit
    summary: "State exits are missing for a lost key, a certificate mismatch, and the recovery commands"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:652"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Partial backup copies are cleaned up only after a successful backup"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:431"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Unexpected exceptions on the call path have no stated handling"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:312"
  - id: F007
    severity: concern
    category: data-integrity
    summary: "The set-aside store is named differently from the parent, and the design does not cover writes after the join or a partial `leave`"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:218"
  - id: F008
    severity: concern
    category: hidden-dependency
    summary: "A local machine is created on first use, which is a silent default owner"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:370"
  - id: F009
    severity: concern
    category: architecture
    summary: "The `door` import rule cannot hold as written"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:105"
  - id: F010
    severity: concern
    category: proportionality
    summary: "The design is larger than its plan entry, with cuts to name"
    location: "project-documents/user/slices/260-slice.hub-and-door.md"
  - id: F011
    severity: note
    category: integration
    summary: "The existing `Door` vocabulary and the parent's door-of-call rule are not addressed"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:244"
  - id: F012
    severity: note
    category: architecture
    summary: "Joined-machine behavior is written as permanent where it applies only to 260"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:163"
  - id: F013
    severity: note
    category: architecture
    summary: "Backups live in a configured directory outside the state directory, without recording the exception"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:401"
  - id: F014
    severity: note
    category: scope
    summary: "Two plan criteria are reworded without being listed"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:551"
  - id: F015
    severity: pass
    category: scope
    summary: "Served operations, owner tables and dependencies match the plan and the current schema"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:38"
---

# Review: slice — slice 260

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] A plan success criterion is deferred to 262 without a valid reason

The plan's 260 criterion (260-slices, line 45) requires that a `standing` set from one machine is read by `decisions` and by `standing` on the other. The design replaces it with a `standing` replay (line 544) and a `decisions` check over seeded records (line 546). The departure row cites `list`, which the criterion does not name. The valid part is that a standing answer appears in `decisions` only when an answer cites it, which needs 262's `handle_pause`. That does not justify dropping the check. The fixture can call `standing` through the door, stop the hub, seed an answer whose source is `standing:<id>` with the store's own functions, restart, and assert that `decisions` from the other machine shows it. Keep the check in 260, or ask the PM to change the plan.

### [CONCERN] The join certificate fetch has no stated TLS setting and conflicts with the parent's connection rule

Step 3 fetches the certificate "from the TLS handshake, without sending any request." D5 specifies the TLS setting only for calls (line 235). Reading an unknown certificate means accepting it without verification and then comparing its fingerprint. The parent's Technical Considerations say the client connection "is not done by turning checking off and comparing afterwards." The join is safe if the fingerprint comparison gates the token and no request bytes are sent before it, but the design must say that and record the exception against the parent. Success criterion line 548 also says a wrong certificate "fails in the handshake," which is not what join does. It fails with `JoinError` after the handshake (line 213).

### [CONCERN] The unknown-outcome rule departs from the parent without being listed

The parent's "Repeats and failures" section says an unknown outcome tells the caller to read the state (`inbox`, `list`) before sending anything again. The design says to run the same command again. `inbox` and `list` are not served in 260, so some departure is forced, but the design does not record one. For `standing` and `withdraw`, the design names no served read that shows the standing answer's state, so the compare-and-set reply is the only check. The design should say so, list the departure, and state the advice per operation. The walkthrough's "running it again is safe" (line 645) depends on the same unstated premise.

### [CONCERN] State exits are missing for a lost key, a certificate mismatch, and the recovery commands

- **Lost key or certificate, no backup.** The walkthrough says the way on is `--from-backup` (line 652). The design also allows a hub to serve with an unwritable `backup_dir` (criterion line 559; walkthrough line 640), so a hub may never have a backup. The remaining path is to start on an empty state directory and re-invite and re-join every machine. The design does not say so.
- **Certificate mismatch.** The client error (line 239) says only that the hub "did not present the saved certificate." Unlike the bad-token message (line 271), it names no way back, and the walkthrough does not cover it.
- **Recovery commands.** The mode-switch table (lines 157–164) lists neither `join` nor `leave`. The D3 loader fails on a missing certificate. If `leave` goes through that loader, a machine with a missing certificate cannot leave. The design should say which commands bypass the loader.

### [CONCERN] Partial backup copies are cleaned up only after a successful backup

Each attempt writes under a `.partial-` name and renames on success. Leftover partials are removed only after a successful backup (line 431). A copy that fails partway, for example on a full backup disk (line 416), leaves a partial copy of the store and key. The check retries every five minutes (line 419), so each partway failure adds another. The cleanup needs a success, and a success needs the space those partials use. The design should delete an attempt's own partial when that attempt fails, and state what bounds the rest.

### [CONCERN] Unexpected exceptions on the call path have no stated handling

Line 264 limits `hub_error` to today's operational errors. Line 312 says any raise in the operation is refused as `hub_error`. Neither says what happens to a non-operational exception, such as a bug or the owner trigger's abort (line 365), which raises an integrity error. The Exception Handling rule requires the boundary handler to log the traceback at ERROR with `logger.exception`. The refusal line (line 444) is one line with no traceback. The design should name the boundary handler, the entry it writes, and whether the client gets `hub_error` or a separate code.

### [CONCERN] The set-aside store is named differently from the parent, and the design does not cover writes after the join or a partial `leave`

The parent's Machines section says `--set-aside-local` renames the store "to a dated backup." The design uses the fixed name `amoeba.sqlite3.set-aside`, and the departures table does not record the change. A command already running finishes its writes into that file, and the hub never sees them (line 657 calls this "one limit"). The local way opens or creates the store as it does today, and nothing refuses that while a set-aside file exists. Depending on the order `leave` uses, a failure partway can leave the machine on an empty new store while the data sits in the set-aside file. The design should use the parent's dated name or record the change. It should reuse the parent's adopted-mark idea so that a local write checks a mark before committing. It should also state `leave`'s step order and what happens when the store path is already occupied.

### [CONCERN] A local machine is created on first use, which is a silent default owner

The parent says the migration gives the local store one machine standing for the install (How the build gets there). The design moves that to first use. The first insert that needs an owner creates the `local` machine in the same transaction, across twelve insert paths. A store with no acting machine set acts as `local` (lines 369–370). The rationale is sound: a migration would put a `local` machine in every hub store (line 490). The mechanism is still a silent default, which the Core Principles forbid. A missed `act_as` on the hub would attribute records to `local` without an error, and the planned test catches that only after a fixture run. The design should create `local` explicitly where the local way opens its store, and make a store with no acting machine fail.

### [CONCERN] The `door` import rule cannot hold as written

The rule says `door` imports nothing from `store` and may import `operations.names`. The `operations.names` module imports `store.vocabulary` for `Door`, so any `door` module that imports it reaches `store`. If `tests/test_import_boundaries.py` follows imports transitively, the rule fails on the first run. If it checks direct imports only, it leaves a path to `store` that the rule is meant to close. The design should keep the served-list constants as plain values in `door.protocol`, or state the exception.

### [CONCERN] The design is larger than its plan entry, with cuts to name

Cut or fold these:

1. **Backup-overdue flag in `hub machines`** (lines 385, 389; criterion 559; walkthrough 640). The plan and the parent ask for last-called time and client version. A failed backup is already logged at error level (line 416). Drop the derived flag, or show the failure in the log only.
2. **Hello probe in `join --address`** (line 222). The plan says `--address` "changes only the address" (plan line 38; parent "Machines" section). Restore that behavior.
3. **`docs/door-contract.md`** (line 474) restates D6 to D10. The parent names five contract documents (Related Work). Fold the door text into `docs/cli-contract.md`, or keep D6 to D10 as the single source.
4. **Implementation order** (lines 611–625) belongs in the task breakdown. **Review history** in the walkthrough (line 655) belongs in the notes.
5. **Config-example equality test** (line 451) duplicates the example text. Keep one source.

### [NOTE] The existing `Door` vocabulary and the parent's door-of-call rule are not addressed

The store records a `Door` value (CLI or MCP) on answers, and a test pins it. The parent says the client sends the door a call came through, and the wake-command rule depends on it. The call format (line 246) has no door field, and the design does not mention `Door`. I checked the six served operations: none takes a door parameter, so 260 is unaffected. Slice 262's `answer` and 263's MCP calls will need it. The design should name the field that carries it and the value the hub records for a network call. The new `door` package name also collides with the existing `Door` concept.

### [NOTE] Joined-machine behavior is written as permanent where it applies only to 260

Line 163 says the `answer` deadline check "reads the local config, runs only with no client file." The parent and plan 263 move that check to the hub. Since 260 does not serve `answer`, nothing changes here, but the table presents the local check as the rule. Line 168 says a running `amoeba-mcp` whose store closes stops presence, with only a log line, so its push stops silently. That is acceptable in 260, because only fixtures join, but the design should say so. It should also give the hub's address in that error, as D2 does for `NotServedError`.

### [NOTE] Backups live in a configured directory outside the state directory, without recording the exception

The Amoeba rule places databases in the state directory. The parent requires backups on a different disk, so `backup_dir` is a justified exception. D1 is silent about it. Record the exception and its reason in D1.

### [NOTE] Two plan criteria are reworded without being listed

Plan criterion 3 says the hub is "killed between the commit and the reply." The design tests a dropped reply followed by an in-process restart (line 460). The SQLite state is the same, but the wording differs. Either run a real process kill on the fixture, or note the equivalence. The plan's live-store criterion is met at release through `update_live.py` (line 478). The slice should run that migration as a step and record the restore path in its notes, as the plan says.

### [PASS] Served operations, owner tables and dependencies match the plan and the current schema

The six served operations (line 38) match the plan's 260 list, and the exclusions for 261 to 264 match its assignments. The twelve owner-bearing tables (line 362) match the tables in migrations 001 to 010, once `schema_meta` and `pm_marker` are excluded. `starlette`, `uvicorn` and `cryptography` are installed through `mcp` (`uv.lock`), so the "nothing new installed" claim holds. The `wiring.invoke`, `open_state_store`, `OPERATIONAL_ERRORS`, WAL mode and 5-second busy-time references also match the code.

### Run Digest

- Response length: 14005 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 2030228 / 1807747 / 222457 / 106808 / not computed
- Duration: 488.1 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
