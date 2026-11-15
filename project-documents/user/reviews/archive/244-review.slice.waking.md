---
docType: review
layer: project
reviewType: slice
slice: waking
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/244-slice.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: d635accf92a2eeece78bd5b9d5f0a88112bf114b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 1144729
cachedTokens: 899018
cacheWriteTokens: 245697
completionTokens: 71029
durationSeconds: 340.1
costUsd: 0.455745
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "A wake command whose wrapper died has no exit Amoeba enforces"
    location: "project-documents/user/slices/244-slice.waking.md:187"
  - id: F002
    severity: concern
    category: limits
    summary: "A failed start never counts toward the daily limit, so the limit does not bound wrapper spawns"
    location: "project-documents/user/slices/244-slice.waking.md:126"
  - id: F003
    severity: concern
    category: architecture
    summary: "Every request send opens a second store connection and takes a write lock, including for members with no wake command"
    location: "project-documents/user/slices/244-slice.waking.md:128"
  - id: F004
    severity: concern
    category: architecture
    summary: "Who may set a wake command is wider than the architecture and plan say, and the design's notice exemption assumes otherwise"
    location: "project-documents/user/slices/244-slice.waking.md:117"
  - id: F005
    severity: concern
    category: security
    summary: "The failure detail can print a secret that the design says must never appear"
    location: "project-documents/user/slices/244-slice.waking.md:118"
  - id: F006
    severity: concern
    category: operator-walkthrough
    summary: "A `lost` row tells the PM a command may still be running when none started"
    location: "project-documents/user/slices/244-slice.waking.md:205"
  - id: F007
    severity: concern
    category: proportionality
    summary: "The design is larger than the plan's effort rating, and two parts can be cut"
    location: "project-documents/user/slices/244-slice.waking.md:179"
  - id: F008
    severity: note
    category: verification
    summary: "The wake step's store-wait count may omit the legacy-move lock on its second open"
    location: "project-documents/user/slices/244-slice.waking.md:217"
  - id: F009
    severity: pass
    category: integration
    summary: "Integration facts match the existing code and the sibling designs"
    location: "project-documents/user/slices/244-slice.waking.md:159"
---

# Review: slice — slice 244

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] A wake command whose wrapper died has no exit Amoeba enforces

After a SIGKILL, the design leaves the command running, marks the row `lost` at its deadline, and does not stop the command. The exits left are the command's own cost cap and a manual kill by the PM. This fails the Amoeba design rules in three ways:
- **Every state has an exit.** The orphan's exit is the cap, and D12 (line 222) only says a wake command "should carry its own cost cap." A command without one runs indefinitely.
- **Every limit says what happens when hit.** `wake_timeout_seconds` is hit for an orphan and nothing happens. Line 56 says "the timeout is the exit" for wake commands, which contradicts line 187.
- **No deferral.** Line 55 excludes "Stopping a command whose wrapper was SIGKILLed." The architecture (arch line 169) requires that "the wrapper itself stops a command that runs past that time." The exclusion removes in-scope behavior.

The stated reason is that Python's standard library cannot read a process start time portably. That does not rule out an identity check through an OS tool such as `ps -o lstart=`, which needs no new Python dependency. The design should evaluate that. Leftover group members after a normal `exited` are the same gap and are not discussed. A fix would record the command's start time when the group is recorded, then stop an unended row's group in the sweep or the next `send` only after checking that identity. The manual kill can stay as a fallback, not as the exit.

### [CONCERN] A failed start never counts toward the daily limit, so the limit does not bound wrapper spawns

D2 says the limit "bounds a retry loop." D5 (line 167) and D7 (line 194) say `start_failed` rows do not count. A member whose command cannot be found gets a new row and a new wrapper process on every `send` to it and every same-id retry, with no cap. Only retention bounds the rows. No agent runs, so this is not spend, but the limit's stated job ("bounds how many such runs a member can start," arch line 170) is false for this case. Either correct D2 and state what bounds spawns, or give failed starts their own small cap with a stated exit.

### [CONCERN] Every request send opens a second store connection and takes a write lock, including for members with no wake command

`claim_wake` runs in `BEGIN IMMEDIATE` after every `sent` or open `unchanged` request. Check 1 (has a wake command) runs inside the lock. Most members have no wake command, so most sends pay for a second connection and a write lock to reach a no-op. The project pattern is to read first and write only when something is due (240's `sweep_messages`, 241's presence). Suggested fix: run a read-only pre-check (wake command set, no live session, no `LIVE_WAKE` row, under the limit), open the write transaction only when it passes, and re-run the checks inside the transaction, which stays authoritative. The wake command could also be read on `send`'s existing connection, so a no-command send never opens the store again.

### [CONCERN] Who may set a wake command is wider than the architecture and plan say, and the design's notice exemption assumes otherwise

The architecture says waking "starts a command the PM configured for that member" (arch line 57). Plan entry 5 says the command is set through `add`, and cites "229: every member setting is set from the CLI" (240-slices line 95). D1 makes it settable from the CLI and the MCP `add` tool, and lets an agent in one repo set it for another member through `add --project`. The departures section (lines 225–235) does not list this. The trust assumption (arch line 71: every agent acts for the same PM) could justify it, but the design should say so as a departure, and should correct the plan citation it contradicts.

The same line creates an internal contradiction. D9 (line 205) says "A wake command is not other repos' text, so it does not set the notice." Under D1, another repo's agent can write the command, which is text from another repo. Either restrict the cross-member case or apply the notice when a command was set by another member.

### [CONCERN] The failure detail can print a secret that the design says must never appear

D1 says the command "must carry no secret" because `list` and `status` print it. A start failure stores the error text (D6, line 176), and for a failed exec that text includes the executable name. A mistaken env-assignment form such as `ANTHROPIC_API_KEY=... claude -p` (D1 says these need a script) is split by `shlex` into an executable whose name holds the secret. The "no such file" error then stores that name in `wakes.detail`, which is kept for the retention window, and prints it in `list` and `status`. The design should either record only the error class and not argv text, or reject at `add` a first token containing `=`, so the mistake fails at setting time.

### [CONCERN] A `lost` row tells the PM a command may still be running when none started

D9 renders every `lost` row as "its command may still be running (process group <pgid or none recorded>)." Line 175 produces a `lost` row with no command started, when the wrapper cannot open the store or read its row. The walkthrough (line 345) then sends the PM to inspect a process that does not exist. A null `command_pgid` does not prove that no command started, because the wrapper can crash between `Popen` and the pgid write. The display should say "no command recorded; the log at `<path>` shows what happened," and not claim a process may be running.

### [CONCERN] The design is larger than the plan's effort rating, and two parts can be cut

The plan rates this slice at relative effort 3 (240-slices line 108), below 241 (4) and 240 (5). The design has twelve decisions, a new column with its own write and failure branch, a status shape with four sub-structures, five contract docs, and a fixture agent with three modes. Two cuts meet the requirement:
1. **`command_pgid`** (the column, the second write after `Popen`, its `StoreBusyError` branch, and the `lost` pgid text). `start_new_session` makes the group id equal the command's pid, so the wrapper can write that pid to its own stderr log at spawn. The log path is already on the row and in `list`. This removes a column, a write and a failure branch.
2. **`next_slot_at`** (D7 line 192 and D9 line 205). The plan and architecture require `list` to show that waking stopped and why, not when. "Waking stopped: N of M wakes used in the last 24 h" meets that. The walkthrough's "when the next slot opens" (line 346) would then change.

### [NOTE] The wake step's store-wait count may omit the legacy-move lock on its second open

D11 counts three store waits: open, claim and failure write. 240 counts the legacy-move lock, the open and the transaction as three separate waits (240-slice.requests.md line 105). `wake_after_send` opens its own connection, so if the legacy-move wait is separate from `open_store`, the step has up to four waits, or 20 s. The bound becomes 155 s, still under `MCP_CALL_DEADLINE_SECONDS` (180 s), so the conclusion holds. The design should state which count `open_store` uses, so the test constant is right.

### [PASS] Integration facts match the existing code and the sibling designs

I checked these against the repo's code and the 240–243 designs:
- `project_of` returns the Context Forge `projectPath`, which D4 relies on.
- `start_child` returns at once with a waitable child or a `LaunchError`, and the D5 `deps.spawn` call matches its signature.
- `terminate_group` sends SIGTERM, waits five seconds, then sends SIGKILL, as D6 describes.
- Prune's rule for unlisted log files removes `logs/wake/` by age, as D10 says.
- `resolve_amoeba_script` exists for 242 to move.
- 243's note path does not reach the request branch that hosts the hook.
- 241's `live_member_ids` signature matches the claim's call.
- Dependencies on 241 and 242 are stated, and the ordering to schema 9 is consistent.

The worst-case `send` bound also holds: 105 + 30 (242) + 15 (244) = 150 s, under 180 s.

### Run Digest

- Response length: 9314 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1144729 / 899018 / 245697 / 71029 / not computed
- Duration: 340.1 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
