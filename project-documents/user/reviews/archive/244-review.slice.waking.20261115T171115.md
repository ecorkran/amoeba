---
docType: review
layer: project
reviewType: slice
slice: waking
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/244-slice.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: bddd3cf305f44f5a62601525e21f924bd44ff786
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
effort: xhigh
turns: 22
promptTokens: 1306418
cachedTokens: 1111094
cacheWriteTokens: 195304
completionTokens: 79780
durationSeconds: 385.4
costUsd: 0.437821
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: dependencies
    summary: "Undeclared dependency on 242, and an empty interfaces list"
    location: "project-documents/user/slices/244-slice.waking.md:6-9"
  - id: F002
    severity: concern
    category: correctness
    summary: "Requests a wake leaves behind are never worked again"
    location: "project-documents/user/slices/244-slice.waking.md:122"
  - id: F003
    severity: concern
    category: error-handling
    summary: "SIGKILL orphan: a second command runs beside the first, the timeout is not enforced, and `list` cannot show it"
    location: "project-documents/user/slices/244-slice.waking.md:172"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Wrapper failures before the child starts are not enumerated"
    location: "project-documents/user/slices/244-slice.waking.md:163-168"
  - id: F005
    severity: concern
    category: operability
    summary: "Operator walkthrough reports no dead ends where there are several"
    location: "project-documents/user/slices/244-slice.waking.md:322-333"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Proportionality: mechanisms the slice does not use"
    location: "project-documents/user/slices/244-slice.waking.md:166-168"
  - id: F007
    severity: note
    category: correctness
    summary: "`next_slot_at` is wrong once the count exceeds the limit"
    location: "project-documents/user/slices/244-slice.waking.md:177"
  - id: F008
    severity: note
    category: error-handling
    summary: "\"Never fails `send`\" is narrower than the handling, and the spawn-skip is unstated"
    location: "project-documents/user/slices/244-slice.waking.md:133"
  - id: F009
    severity: note
    category: security
    summary: "`wake_command` is a secrets and blast-radius surface"
    location: "project-documents/user/slices/244-slice.waking.md:114"
  - id: F010
    severity: pass
    category: integration
    summary: "NFR bound arithmetic matches the parent slices"
    location: "project-documents/user/slices/244-slice.waking.md:202"
  - id: F011
    severity: pass
    category: integration
    summary: "Liveness, note-path and log-prune integration match the producing slices"
    location: "project-documents/user/slices/244-slice.waking.md:65"
---

# Review: slice — slice 244

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Undeclared dependency on 242, and an empty interfaces list

The frontmatter declares `dependencies: 240, 241` and `interfaces: []`. The body needs 242 in two places: the live store at schema 8 from 242's migration (line 60), and `Deps.amoeba_script` (lines 61 and 246). "Interfaces Required" (lines 63-66) omits 242 as well. Migration 8 also needs 241's migration 7 (242, line 60). 241 declares `interfaces: [243, 244]`, so 244 is an interface partner of 241 but says `[]`. The 244 entry in the slice plan (`240-slices.agent-messaging.md`) says "Dependencies: 240, 241", so the plan carries the same gap. List 242 in the frontmatter and in "Interfaces Required", and have the docs step amend the plan entry.

### [CONCERN] Requests a wake leaves behind are never worked again

The only wake trigger is `send`. Line 122 says a retried `send` that answers `unchanged` does not wake, "the first call already decided." That is false when the first call's wake step failed. The uncovered cases:
- A woken agent accepts a request, then times out, exits or is killed. The request stays `accepted`. Accepted has no timeout (architecture, line 101), and no wake reads it. Only a new send or a PM `cancel` moves it.
- A start fails (lines 155-158). The request stays `open`. The walkthrough's fix, "the next request wakes it" (line 325), never reaches this request.
- The wake step hits a `StoreError` (line 133). The sender's 240 retry with the same id answers `unchanged`, so no wake is attempted.
- A request arrives after the woken agent's last `inbox` read (line 131). Line 53 says it waits "as the plan says," but the plan's wake entry says only that a second request during a wake is in the woken agent's inbox. "Waits for the next agent" appears in the plan only for the daily limit.
- An idle live session suppresses the wake (line 126), so the request waits for it or expires (line 330).

Each case has an exit (TTL, or a PM `cancel`), so the state rule holds. The value statement, "a request to a repo nobody has open gets worked without anyone opening it," does not hold for these. Either re-attempt the claim when a wake ends with open or accepted requests and the daily limit allows, or record the gap as a departure and correct line 53 and line 122.

### [CONCERN] SIGKILL orphan: a second command runs beside the first, the timeout is not enforced, and `list` cannot show it

After a SIGKILL, the row reads as gone at its deadline, `WAKE_RUNNING` clears, and a new wake starts while the orphan keeps running. That conflicts with three things:
- The architecture states "One wake at a time per member" (architecture, Waking section). The departures list (lines 210-218) does not mention this.
- The architecture and the plan both say the wrapper stops a command past `wake_timeout_seconds`. The orphan has no timeout. Line 299 says `wake_timeout_seconds` bounds run time, which is false after a SIGKILL. Line 172 says "the slice does not try to find the orphan," which the no-deferral rule does not accept as written.
- `running` covers only live rows and `last_problem` only ended rows (lines 189-190). An unended row past its deadline appears nowhere, so the PM cannot see that a command may still be running.

Record the child's process group and start time on the row, so the next claim or the sweep can signal a group whose recorded start time still matches (this avoids trusting a reused pid). Show unended rows past their deadline as `lost` in `list`. Write the chosen mechanism into D6.

### [CONCERN] Wrapper failures before the child starts are not enumerated

D6 covers a child that fails to start (`OSError`) and a failed final write. It does not cover the wrapper failing earlier: the store cannot be opened or read, or the row cannot be read. Step 1 covers only a missing or already-ended row. In those cases the wrapper exits 3 with nothing recorded. The row stays unended, `list` shows "running since" for a command that never started, and `WAKE_RUNNING` blocks new wakes until the deadline. The design also says the wrapper "needs the store and the state home, not the config," but the live-store step says every `amoeba` command fails without the new keys. State which open path `wake-run` uses. On any failure before the child starts, try `finish_wake(start_failed, reason)`.

### [CONCERN] Operator walkthrough reports no dead ends where there are several

Line 332 says "Dead ends found: none with nobody able to act." Walking the design turns up the following:
- Line 325 gives the wrong fix for "Context Forge has no path." The path is Context Forge's `projectPath` (D4), so `amoeba add --wake-command` does not fix it. The fix is in Context Forge.
- Line 326 says "the next request can wake again," which does not re-wake a request already stuck `accepted` or `open` (see the stranded-requests finding).
- Line 330 treats an idle live session as a trade, not a dead end. The request is stuck until its TTL.
- Line 328 says a killed wrapper's command "may still run" and nobody sees it.

None of these is a dead end with nobody able to act, because the PM has `cancel`, a new `send` and TTL. The walkthrough should say which exit applies to each case and correct the no-path fix.

### [CONCERN] Proportionality: mechanisms the slice does not use

- **`interrupted` outcome, the SIGTERM handler and the `finally` interrupt branch** (D6 steps 2 and 5, the outcome in D3, dev step 3). Nothing in the slice sends the wrapper SIGTERM. Line 54 excludes stopping a command by hand, and the walkthrough has no such path. Cut them, unless the orphan fix above needs the same hook, in which case keep them and say why.
- **`NotWokenReason`** (lines 89 and 124). No output shows it. `wake_after_send` returns a problem line or nothing (line 84), and `list` shows only `stopped` for the limit (line 190). Either surface the other reasons somewhere a person reads them, or return a bool plus the limit state.
- **Risk Assessment, technical risks** (lines 293-295). These restate the architecture's unattended-spend risk (architecture, Technical Considerations). Keep only the wake-specific risks: a checkout with a person in it, and the orphan.

### [NOTE] `next_slot_at` is wrong once the count exceeds the limit

"When the oldest counted wake leaves the window" is the slot time only when used equals the limit. If `max_wakes_per_day` is lowered below the count (for example, 4 used in 24 hours and the limit lowered to 2), the time shown is earlier than the real slot. Define it as the start of the (used − limit + 1)-th oldest counted wake, plus 24 hours.

### [NOTE] "Never fails `send`" is narrower than the handling, and the spawn-skip is unstated

The wake step catches `StoreError`, `LaunchError` and `AmoebaScriptMissing` by type. Any other exception propagates, and `send` then exits 3 for a request that was written. That fits the exception rules, but line 133 says "a problem in the wake step never fails send." Say which exceptions propagate. Also, line 129 says an unknown checkout path inserts a row already ended, while line 95 says `wake_after_send` starts `wake-run` for the claimed row. State that no wrapper is spawned for an ended row.

### [NOTE] `wake_command` is a secrets and blast-radius surface

`list members`, `list -j` and `status` print the command in plain text, and the store keeps it. A command that carries a token leaks it to every reader of `list`. The architecture's rule is that credentials come from environment variables, so the `add` tool text and the contract should say so. Line 116 sends environment assignments to a script, which is the right place. Also, if the MCP `add` tool accepts a member other than the caller's, then an agent in one repo can start unattended runs in another. The architecture's trust assumption covers this, but the design should say it explicitly.

### [PASS] NFR bound arithmetic matches the parent slices

240's `send` worst case is 3 lookups × 30 s + 3 store waits × 5 s = 105 s. 242's `START_BOUND_SECONDS` is 30 s. The wake step adds 3 store waits × 5 s = 15 s. The total is 150 s, under `MCP_CALL_DEADLINE_SECONDS` (180 s). I checked this against 240 ("Timeouts and lost responses") and 242 (`START_BOUND_SECONDS`).

### [PASS] Liveness, note-path and log-prune integration match the producing slices

`live_member_ids(transaction, now, stale_seconds)` matches 241's stated signature. 243 keeps notes in `send_note.py` and places the wake hook only in the request branch (243, line 232), so a note cannot wake. The rule for pruning unlisted logs matches 226's note that `logs/mcp` is unprotected, so `logs/wake` is pruned the same way.

### Run Digest

- Response length: 10261 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 1306418 / 1111094 / 195304 / 79780 / not computed
- Duration: 385.4 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
