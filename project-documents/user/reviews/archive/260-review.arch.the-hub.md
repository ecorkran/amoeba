---
docType: review
layer: project
reviewType: arch
slice: the-hub
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS (all thirteen findings, the fail F001 included, were fixed in the document 20261120, see Resolution)
verdictSource: stated
sourceDocument: project-documents/user/architecture/260-arch.the-hub.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 2b8b72c5e5ffe91be6b843f6dba64b4ca019e6d8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: high
turns: 18
promptTokens: 1127791
cachedTokens: 1022700
cacheWriteTokens: 105065
completionTokens: 12816
durationSeconds: 143.5
costUsd: 1.302392
costBasis: provider
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: completeness
    summary: "The move from in-process to hub across slices 1–4 is undecided, and it conflicts with adoption"
    location: "project-documents/user/architecture/260-arch.the-hub.md#technical-considerations"
  - id: F002
    severity: concern
    category: other
    summary: "One machine's token can plant wake commands that run on every other machine"
    location: "project-documents/user/architecture/260-arch.the-hub.md#the-door-and-access-control"
  - id: F003
    severity: concern
    category: consistency
    summary: "\"Each transaction block becomes one hub call with the same meaning\" doesn't hold for the answering settle"
    location: "project-documents/user/architecture/260-arch.the-hub.md#architectural-principles"
  - id: F004
    severity: concern
    category: completeness
    summary: "A failed call may still have been applied, and retry rules are missing"
    location: "project-documents/user/architecture/260-arch.the-hub.md#the-hub"
  - id: F005
    severity: concern
    category: consistency
    summary: "`hub_retry_seconds` can't come from the hub"
    location: "project-documents/user/architecture/260-arch.the-hub.md#machines"
  - id: F006
    severity: concern
    category: completeness
    summary: "Backups are manual, and hub logs and the refused-call log have no cleanup"
    location: "project-documents/user/architecture/260-arch.the-hub.md#the-hub"
  - id: F007
    severity: concern
    category: completeness
    summary: "`prune` and the calls log aren't placed in the three kinds of operation"
    location: "project-documents/user/architecture/260-arch.the-hub.md#three-kinds-of-operation"
  - id: F008
    severity: concern
    category: completeness
    summary: "A member with no checkout left can't be removed"
    location: "project-documents/user/architecture/260-arch.the-hub.md#operator-walkthrough"
  - id: F009
    severity: concern
    category: feasibility
    summary: "Pending-work pickup across several sessions on one machine is only specified for wakes"
    location: "project-documents/user/architecture/260-arch.the-hub.md#work-that-belongs-to-a-machine"
  - id: F010
    severity: concern
    category: technology
    summary: "The HTTP server, TLS, async model and load tests aren't specified"
    location: "project-documents/user/architecture/260-arch.the-hub.md#technical-considerations"
  - id: F011
    severity: concern
    category: other
    summary: "The hub's certificate and private key are generated state placed under config"
    location: "project-documents/user/architecture/260-arch.the-hub.md#the-hub"
  - id: F012
    severity: concern
    category: feasibility
    summary: "Editing config, and long-running sessions after an upgrade, both get harder"
    location: "project-documents/user/architecture/260-arch.the-hub.md#design-goals"
  - id: F013
    severity: note
    category: completeness
    summary: "Re-addressing the hub requires a new invite for every machine"
    location: "project-documents/user/architecture/260-arch.the-hub.md#machines"
---

# Review: arch — initiative 260

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [FAIL] The move from in-process to hub across slices 1–4 is undecided, and it conflicts with adoption

"Getting there in steps" says the in-process path stays until the last slice, so each slice leaves a working install. Adoption is in slice 5. Three things follow that the document doesn't resolve:

1. **Which store is live during slices 1–4.** Until slice 5 the hub's store is empty and the PM's records stay on the laptop store. Slices 1–4 produce a hub that no real work touches, and the document never says what makes a client choose the hub over the in-process path in the meantime. That switch is a second mode for the length of four slices. "One mode" (Architectural Principles) is the reason the document gives for having no fallback, but it doesn't say how this transitional mode is chosen or tested.
2. **Schema order.** Slice 2 ("Members by name") brings in member names and checkouts, and slice 4 brings in session rows with a machine. In the same slices, the in-process path keeps opening the laptop store. Either those migrations run against the laptop store in place, which makes most of adopt step 3 redundant (member names, one checkout per member, wake commands moved to checkouts, machine on every path), or the in-process code has to keep working on the old schema while the hub code uses the new one. The document describes adopt's migration as if the laptop store were still at today's schema in slice 5.
3. **Registration is cut in slice 2,** and "Everything that resolved other members through `cf` goes." The in-process path still has to resolve recipients after that. The design needs to say how it does.

State the transition model outright. Either migrate the laptop store in each slice and shrink adopt to "copy the file, add the machine and owner", or move adoption to right after slice 1 and serve every later slice from the hub.

### [CONCERN] One machine's token can plant wake commands that run on every other machine

The document says per-machine tokens mean "a machine can be removed on its own without touching the others", and "All machines act as the PM." But registration lets any caller "set a member's or a checkout's settings". Nothing stops machine A from setting the wake command on machine B's checkout. Today that command can be set only from the CLI door (`WAKE_COMMAND_DOORS = {Door.CLI}` in `src/amoeba/operations/add_door.py:23`).

Over the network door, CLI vs MCP is now whatever the client says it is. `amoeba-mcp` reads the same client file and token as the CLI. So a leaked token, or an agent on a less trusted machine, can make code run as the PM on every machine. Revoking the token afterwards doesn't remove the commands it already planted.

The fix costs one rule: only the machine a checkout is on may set or change that checkout's wake command. Then a token can only reach its own machine. Also say what the door check `add_door` does becomes once it is self-asserted.

### [CONCERN] "Each transaction block becomes one hub call with the same meaning" doesn't hold for the answering settle

`settle_answered` (`src/amoeba/store/answers.py:239-259`) takes a `gate: Callable[[int], GateRefusal | None]` and runs it inside its `BEGIN IMMEDIATE` transaction, so two settles can't both pass the limit. A callable can't be sent over a JSON door. To keep the meaning, either the gate logic (`answering/gate.py` plus `AnswererSettings`) runs on the hub, or the call sends the limit as data and the hub applies it.

Either way, this contradicts "only its store reads and its final write are rerouted; nothing else in it is touched" (Technical Considerations). The principle needs a check across the whole store: list every transaction that takes a callback or reads a local value inside it, and say how each one moves.

### [CONCERN] A failed call may still have been applied, and retry rules are missing

The document says "a restart loses at most the request in flight, which the client reports as failed". Over a network, a lost response doesn't mean nothing happened: the hub may have committed. The pause hook retries for `hub_retry_seconds`, an agent seeing "failed" will retry `send`, and `answer` may already have triggered a same-machine resume.

The design needs a third outcome, "unknown", or a client-generated request id that the hub de-duplicates. It also needs a list of which operations are naturally safe to repeat (`handle_pause`, keyed by run and pause) and which aren't (`send`, `reply`, `answer`). Without that, the "loud client" goal produces duplicate requests whenever the hub restarts.

### [CONCERN] `hub_retry_seconds` can't come from the hub

The client file holds "exactly: the hub's address, the fingerprint, the machine's name and its token". Client settings "come from the hub with the first call, so the hub's config is the only one." But `hub_retry_seconds` (Operator walkthrough step 4) is only needed when the hub can't be reached, so it can't be fetched from the hub.

The client-side timeouts for connecting and reading have the same problem. Define a small set of client-local values: either add them to the client file, or make them centralized constants per the project's no-magic-defaults rule. Then say so in the Machines section.

### [CONCERN] Backups are manual, and hub logs and the refused-call log have no cleanup

`amoeba hub backup` exists only as an admin command, and there is no scheduler (that's 300). Walkthrough step 9 ("restore the newest file from the backups directory") and the goal that the hub "loses nothing" both assume backups that nothing creates. Specify an automatic backup, for example `hub serve` running one at start and every N hours on a plain timer thread, or drop the claim.

Separately, "a call without a valid one is refused and logged" and "the hub's logs" in the state directory have no named cleanup. A LAN scanner hitting the port fills the refused-call log without limit. The Amoeba "Every state has an exit" rule requires a named cleanup or a stated bound for each.

### [CONCERN] `prune` and the calls log aren't placed in the three kinds of operation

`prune` (`src/amoeba/operations/prune.py`) reads evidence from the store (open run ids, answering run ids) and deletes local scratch, resume logs, wake logs and the per-call log under `logs_dir`. It isn't in the table. After this initiative, logs are spread across every client ("Logs stay where the work ran") plus the hub.

The design needs to say:
- that `prune` is a "client gathers, hub writes" operation run on each machine, with a store read for evidence
- what triggers it on each machine
- where the calls log lives now: client, hub, or both.

Otherwise client log directories stop being cleaned once the store leaves the machine.

### [CONCERN] A member with no checkout left can't be removed

Step 7 says such a member "stays, with its mail, until `amoeba rm` or a new `add`". But `rm` is a "client gathers, hub writes" operation, and the caller is identified from its local `cf` project mapped to a checkout. Once a member has no checkout, no directory on any machine maps to it, so every caller is `not_a_member`.

The document needs an `amoeba rm <name>` path that works by name. It should also say what happens to open requests addressed to that member, which can no longer be woken.

### [CONCERN] Pending-work pickup across several sessions on one machine is only specified for wakes

Every `amoeba` call and every `amoeba-mcp` tick asks "what should this machine start" and starts it detached. With three sessions open on the laptop, three ticks ask at once. The wake path names "today's claim". The resume relies on `mark_resume_started` being compare-and-set (`resume.py:138-141`), which is fine. But nothing is stated for starting `handle-pause` on a held question when its request ends, which is the third kind of pending work.

Also, the window between "hub marks started" and "client spawns" now crosses the network. A dropped response leaves the record marked started with nothing running. Say which sweep recovers it, and on which machine.

Each pending kind needs its claim and the state its claim leaves on failure.

### [CONCERN] The HTTP server, TLS, async model and load tests aren't specified

The direct dependencies are `anyio`, `mcp`, `pydantic` and `pyyaml`. The document chooses none of the following:
- **The HTTP server.** `starlette` and `uvicorn` are already in `uv.lock` through `mcp`.
- **How the certificate is made.** `cryptography` is in the lock, but making a certificate needs it as a direct dependency.
- **How the clients call out.** The client needs a synchronous HTTP call; `amoeba-mcp` is anyio-async and its tick must not block the loop.
- **How the hub runs store work.** The store is synchronous `sqlite3` with `BEGIN IMMEDIATE`. Under an async server, each transaction must run in a worker thread or a single store thread, or it breaks the project's "<1ms sync inside async" rule. Concurrent requests contending for one connection need a decision: serialize, or one connection per request.

`python.md` also requires a load test for any code on a network or concurrency path. The Testing bullet has only unit tests and a live fixture. Add a load test that asserts latency and that ticks don't starve with N sessions plus CLI calls hitting the hub at once.

### [CONCERN] The hub's certificate and private key are generated state placed under config

"Two mounted directories: config (the config file and the hub's certificate)". The hub generates the certificate and key at first start, and no person edits them. The Amoeba rule "Config is config; state is state" puts files the system writes in the state directory. That also keeps the private key out of a directory the PM edits and may sync or copy. Move the certificate and key to the state mount.

### [CONCERN] Editing config, and long-running sessions after an upgrade, both get harder

The goal "Nothing the PM does today gets harder" fails in two places the walkthrough skips:

- **Changing a setting.** It now means editing a file inside a container's mount on another machine. The document doesn't say whether the hub reads config per call or once at start, or what a bad edit does: does every call on every machine fail, or does the hub keep the last good config?
- **Upgrading.** A door-version bump makes every running `amoeba-mcp` on every machine fail its ticks and tools until that Claude session restarts, and pause hooks on machines not yet updated fail, so those pauses go unrecorded. The walkthrough covers only "a client is older than the hub" for a one-shot CLI call.

Add both to the walkthrough, with the reload rule and what a session does when its door version no longer matches.

### [NOTE] Re-addressing the hub requires a new invite for every machine

The client file pins the address. If the LAN machine's address changes (DHCP, a replacement box restored from backup per step 9), the only path given is a new invite, and so a new token, on every machine. A `join` that updates only the address, or an advice to use a stable hostname, would avoid that. Also say that hostname checking is replaced by the pinned fingerprint, and that the self-signed certificate's expiry is ignored or set far in the future, so the certificate doesn't become a limit with no stated exit.

### Run Digest

- Response length: 12879 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 1127791 / 1022700 / 105065 / 12816 / not computed
- Duration: 143.5 s
- Cost: $1.30 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Resolution

Worked into `260-arch.the-hub.md` 20261120.

- F001 (fixed): new section "How the build gets there". A machine with no client file runs both parts in one process on the local store; one with a client file sends everything to the hub. Schema changes are ordinary migrations on the local store, recipients are found in the store either way, and adoption shrinks to a copy. The last slice deletes the local-store way.
- F002 (fixed): a checkout's wake command can be set only by the machine the checkout is on. The CLI-only rule is kept by the client; the hub's guard is the machine rule.
- F003 (fixed): a check that runs inside a transaction runs on the hub, with the call carrying the values. The pause-path slice lists every such transaction first. The claim that nothing else in the answering pipeline is touched is corrected.
- F004 (fixed): every call carries a client-made id; the hub keeps a writing call's result for `call_result_minutes` and returns it to a repeat. Outcomes are done, refused or unknown.
- F005 (fixed): `hub_connect_seconds`, `hub_read_seconds` and `hub_retry_seconds` are in the client file, filled by the invite from the hub's config.
- F006 (fixed): the hub backs up at start and every `backup_hours`, keeping `backups_kept`. Its log rotates by size with a keep count, and refused calls are lines in it.
- F007 (fixed): clean-up of local files is a client-run operation on today's hourly trigger, asking the hub which runs are open. The calls log stays on the machine whose hook wrote it.
- F008 (fixed): `amoeba rm <name>` works from any machine and directory. Requests to a member with no checkout wait for expiry, or are cancelled by the removal.
- F009 (fixed): each of the three kinds of pending work has a named claim, and a claim that never starts is retaken after a time limit on the hub's clock.
- F010 (fixed): the server library already installed through `mcp`, `cryptography` as a direct dependency, store work in a worker thread on its own connection per request, a blocking client call, and a load test.
- F011 (fixed): the certificate and key are in the state directory.
- F012 (fixed): config is read on each call and a bad edit fails loudly on every machine. The walkthrough covers changing a setting and upgrading, open sessions and pause hooks included. The design goal is reworded to say what moves to the hub machine.
- F013 (fixed): `amoeba join --address` changes only the address; the fingerprint replaces hostname checking and the certificate's end date is never a limit.
