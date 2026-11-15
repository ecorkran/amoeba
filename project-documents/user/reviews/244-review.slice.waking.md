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
reviewedSha: 8a9f8da980e2573e6e0076becbe6dbbfc369403b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 1421523
cachedTokens: 1246634
cacheWriteTokens: 174867
completionTokens: 54937
durationSeconds: 270.5
costUsd: 0.361748
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: security
    summary: "The recipient's wake command inherits the sender's environment"
    location: "project-documents/user/slices/244-slice.waking.md:118, 166"
  - id: F002
    severity: concern
    category: boundary
    summary: "Setting a wake command widens the architecture's \"PM configured\" decision to any agent, across repos"
    location: "project-documents/user/slices/244-slice.waking.md:117, 242"
  - id: F003
    severity: concern
    category: boundary
    summary: "Send, list and status wait on a killed wake's command, against the architecture's \"never waited on\" rule"
    location: "project-documents/user/slices/244-slice.waking.md:191-197, 224-227"
  - id: F004
    severity: concern
    category: exits
    summary: "A killed wrapper's command has no Amoeba exit when nothing else calls Amoeba"
    location: "project-documents/user/slices/244-slice.waking.md:197, 232, 360, 364"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The slice is heavier than its plan entry; the reaper's list and status hook is the cut"
    location: "project-documents/user/slices/244-slice.waking.md:191-197, 242-243"
  - id: F006
    severity: concern
    category: dependency
    summary: "The declared dependencies omit 243, which the note test relies on"
    location: "project-documents/user/slices/244-slice.waking.md:6-9, 60-62"
  - id: F007
    severity: pass
    category: integration
    summary: "Integration points match what 240–242 and the code provide"
    location: "project-documents/user/slices/244-slice.waking.md:58-68"
  - id: F008
    severity: pass
    category: alignment
    summary: "Message text stays out of the command, and failures change no message"
    location: "project-documents/user/slices/244-slice.waking.md:120, 144"
  - id: F009
    severity: pass
    category: failure-modes
    summary: "Failure paths for new I/O calls each have a recorded outcome"
    location: "project-documents/user/slices/244-slice.waking.md:166-189"
  - id: F010
    severity: pass
    category: nfr
    summary: "The send bound is restated with its specific target"
    location: "project-documents/user/slices/244-slice.waking.md:224-227"
  - id: F011
    severity: pass
    category: scope
    summary: "No in-scope behavior is deferred"
    location: "project-documents/user/slices/244-slice.waking.md:52-56"
---

# Review: slice — slice 244

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The recipient's wake command inherits the sender's environment

D1 says the wake "inherits the environment of the process that called send, not the recipient's shell," and D5 starts it through the existing spawn, which passes the caller's environment. The sender is another repo's agent or pipeline run. So the command the recipient's PM configured runs with the sender's variables: API keys, Git or cloud tokens, and a per-run budget setting. An agent woken this way can spend under the sender's key, outside the recipient's `max_wakes_per_day` and its own cost cap. The architecture's Waking and Technical Considerations sections bound unattended spend by the wake command's own cap, and say nothing about credentials crossing repos. D1 gives reliability as the only reason for inheritance. Fix: spawn with an explicit, minimal environment, and state the trust decision in the architecture.

### [CONCERN] Setting a wake command widens the architecture's "PM configured" decision to any agent, across repos

The architecture's Changes table says waking "starts a command the PM configured for that member." D1 lets any agent set the command through the MCP `add` tool, including `add --project` for another member. The next request to that member then runs the command in a repo nobody has open. Departure 242 asks the docs step to reword the architecture to "by the PM or an agent acting for the PM," which writes the wider authority into the parent as a wording fix. That changes who can start unattended work, so it needs an explicit architecture decision. Fix: either narrow D1 to the CLI, or record the widened authority as its own decision before build.

### [CONCERN] Send, list and status wait on a killed wake's command, against the architecture's "never waited on" rule

The architecture's Waking section says "the wake process is never waited on, and its failure changes no message." The reaper does wait. It sends SIGTERM to the orphan's group and polls up to `TERMINATE_GRACE_SECONDS` (5 s) before SIGKILL, after a `ps` call of up to 2 s. D6 runs it in `wake_after_send` for the recipient, and in `wiring.invoke` for `list` and `status` for any member. D11 counts the wait in `send`'s bound (37 s). Departure 243 mentions the reaper but not that a request path waits on the orphan. The 240 worst-case timing test covers only send, inbox, reply and cancel, so `list` and `status` now have up to seven seconds of wait with no test. Fix: name the wait as a departure and add `list` and `status` to a timing test, or drop their reaper hook (see the proportionality finding).

### [CONCERN] A killed wrapper's command has no Amoeba exit when nothing else calls Amoeba

D6 says that for an orphan of a member that gets no request and no `list` or `status`, the timeout "is not enforced" and the command "runs until its command ends." The only bound left is the wake command's own cost cap, and D12 says it "should carry" one. The architecture says each wake command carries its own cost cap. The operator walkthrough then reads "Dead ends found: none where nobody can act" (line 364). With no cap in the command, no Amoeba command ends the run, and the PM can only kill the process by hand. That breaks the "every state has an exit" and "every limit says what happens when hit" rules. Fix: make the cap a required element of the contract, with a test that the example carries one, and name the manual stop in the walkthrough as the explicit exit. Alternatively, bound the orphan inside Amoeba.

### [CONCERN] The slice is heavier than its plan entry; the reaper's list and status hook is the cut

The plan gives Waking a relative effort of 3, and the architecture's Design Goals say the design stays small with no new process kept running. This design has twelve decisions, eleven departures, six new store and operation modules, a `ps` identity check, a process-group reaper, a live migration, a fixture agent, and four contract docs plus the `add` tool text. The largest addition is the reaper, which neither the plan nor the architecture mentions. One cut meets the requirement with less: drop the `wiring.invoke` reaper hook for `list` and `status`. The send-path reap for that member already runs before any new claim, which is what "one wake at a time" needs. Dropping the read-path hook removes a read that signals other members' processes and adds up to seven seconds to reads. The cost is that a lost row shows only after the next send to that member. Each remaining mechanism should be justified against the architecture's "small."

### [CONCERN] The declared dependencies omit 243, which the note test relies on

The frontmatter lists 240, 241 and 242. The Integration Points (line 275) and Success Criteria (line 282) depend on 243's note path, which never reaches the wake hook. A test sends a note to a member with a wake command, and that test cannot be written without 243. The plan's order (240 → 241 → 242 → 243 → 244) builds 243 first, so this is a gap in the declared dependencies, not a build-order failure. Fix: add 243 to the frontmatter and to Prerequisites.

### [PASS] Integration points match what 240–242 and the code provide

Checked against the 240–242 designs: `resolve_recipient`, `live_member_ids(transaction, now, stale_seconds)`, `session_stale_seconds`, `Deps.amoeba_script`, `START_BOUND_SECONDS`, and the migration chain 6 → 7 → 8 → 9. In the code, the existing detached start (exclusive logs, a new session, no stdin) and `terminate_group` (SIGTERM, grace, SIGKILL) match the description. Prune removes unlisted log directories by age, so `logs/wake/` is pruned as D10 says. `prune_after_days` is enforced at a minimum of 1, so retention cannot delete wake rows inside the 24-hour count window.

### [PASS] Message text stays out of the command, and failures change no message

D1 passes nothing from the request to the command (no argv, environment or stdin text). D9 applies the quoted-data notice to results that show a command. D2 reports store and start failures in `wake_problem` and leaves the request as written. That matches the architecture's "no silent drops" and "failure changes no message" rules.

### [PASS] Failure paths for new I/O calls each have a recorded outcome

Spawn failure, a missing `amoeba` script, a store that cannot be opened before the command, an unsplittable or missing executable, an unexpected error after start, a `ps` failure, and a failed final write each name a recorded outcome, a log line and an exit code. The one gap is the reaper's signal call: an `EPERM` from `killpg` is not listed in D6 (lines 191–195).

### [PASS] The send bound is restated with its specific target

The 240 worst-case test for `send` (105 s) is restated with the wake's addition (37 s, `WAKE_BOUND_SECONDS`), giving 172 s against `MCP_CALL_DEADLINE_SECONDS` (180 s). A recipient with no wake command adds nothing. The `list` and `status` gap is covered in the send-path finding above.

### [PASS] No in-scope behavior is deferred

The exclusions are the ones the plan and architecture already make: choosing the work, waking for notes, a manual stop, and detecting whether mail was read. None is plan-assigned behavior pushed to an issue or a later slice. The null-path fix in Context Forge is an external dependency, not a deferral.

### Run Digest

- Response length: 9902 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 1421523 / 1246634 / 174867 / 54937 / not computed
- Duration: 270.5 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11

## Resolution

- [concern] The recipient's wake command inherits the sender's environment: fixed. D1 and D6 now build the command's environment explicitly from `WAKE_ENV_NAMES` (`PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LC_ALL`, `TMPDIR`, `AMOEBA_HOME`) and nothing else. A departure has the architecture record the decision, and a success criterion tests that a marker variable does not reach the command.
- [concern] Setting a wake command widens the architecture's "PM configured" decision to any agent, across repos: kept wide and recorded as its own decision, not a wording fix. The departure now says any agent acting for the PM may set it from either door, with the reasoning (narrowing to the CLI would not stop an agent with a shell) and what bounds it. The docs step writes it into the architecture's Changes table and amends the plan entry.
- [concern] Send, list and status wait on a killed wake's command: fixed. The reaper now sends SIGKILL at once and does not wait, so `TERMINATE_GRACE_SECONDS` is out of `WAKE_BOUND_SECONDS` (now 32 s; `send` totals 167 s). The `list` and `status` hook is removed (next finding).
- [concern] A killed wrapper's command has no Amoeba exit when nothing else calls Amoeba: partly fixed. The wake-command contract now requires a cost or time cap, with a docs test that the example carries one. `list` shows an unended row past its deadline as overdue with the command's pid and log path. The walkthrough names the PM's manual stop as the one explicit exit and reports it as a dead end. I did not add an in-Amoeba bound, because Amoeba keeps no resident process.
- [concern] The slice is heavier than its plan entry; the reaper's list and status hook is the cut: applied. The `wiring.invoke` hook is dropped, and the reaper runs only in `wake_after_send` before the claim. D6 gains a short "Why this size" paragraph justifying the remaining reaper.
- [concern] The declared dependencies omit 243: fixed. 243 is in the frontmatter and Prerequisites, and the departures list amends the plan entry to 240, 241, 242, 243.
- [pass] Integration points match what 240–242 and the code provide: no change needed.
- [pass] Message text stays out of the command, and failures change no message: no change needed.
- [pass] Failure paths for new I/O calls each have a recorded outcome: no change needed.
- [pass] The send bound is restated with its specific target: no change to the target. The figure is recomputed after the reaper no longer waits (32 s, 167 s total).
- [pass] No in-scope behavior is deferred: no change needed. No issues were filed.
