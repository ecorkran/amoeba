---
docType: review
layer: project
reviewType: slice
slice: request-runs
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/184-slice.request-runs.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 825d02a2298f6023a1259c6fea38592295cb119c
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 117940
cachedTokens: 11162
cacheWriteTokens: 106774
completionTokens: 7581
durationSeconds: 63.1
costUsd: 0.504873
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction and tick placement match the architecture"
    location: "project-documents/user/slices/184-slice.request-runs.md#Architecture"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/184-slice.request-runs.md#D7"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "D13 narrows an architecture-level guarantee, but only the slice plan is amended"
    location: "project-documents/user/slices/184-slice.request-runs.md:330-336"
  - id: F004
    severity: concern
    category: failure-modes
    summary: "Crash adoption (D7 step 4) is under-specified and conflicts with the spawn ordering"
    location: "project-documents/user/slices/184-slice.request-runs.md:261-265"
  - id: F005
    severity: concern
    category: consistency
    summary: "Internal inconsistencies in the request vocabulary and the bind signature"
    location: "project-documents/user/slices/184-slice.request-runs.md:195"
  - id: F006
    severity: note
    category: scope
    summary: "Proportionality"
    location: "project-documents/user/slices/184-slice.request-runs.md#Technical-Scope"
---

# Review: slice — slice 184

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Boundaries, dependency direction and tick placement match the architecture

- The request stage runs inside the Runner's tick, after the program stage and plan reads and before the view is built (lines 130-146). That is the architecture's "program stage in the tick" principle.
- `runner/lifecycle` receives only node-id sets through `ProgramReadiness`, never the program store (line 124).
- The provider's tick is the only writer of request rows and of the one-time `bind_edge`. The asker's tick keeps 183's writes.
- No new tenant, process or git verb is added. `git_read` stays on `status` and `log`.
- The checkout exemption applies only when no run is in flight and the tree is clean and on the target, as the architecture states.

### [PASS] Failure modes are enumerated for each new I/O path

Each new path has a named outcome:
- **Launch:** I/O directory, `need.md` and spawn failures give `launch_failed` (D7).
- **Run outcome:** failed, paused, orphaned and vanished runs give `run_failed` (D8).
- **Reply:** a missing or malformed reply is a named failure.
- **Head read:** a failed read leaves the request `running` and is retried (D8).
- **Plan read:** a failing plan read leaves `awaiting_plan_read` beside `plan_read_failed` (D9).
- **Recovery:** `run_lost` (D8).
- **Timeout:** the absence of a timeout is an explicit, justified decision (D6).

All of these surface on `program-blocked` (D15).

### [CONCERN] D13 narrows an architecture-level guarantee, but only the slice plan is amended

- The architecture says request slices "have no implicit predecessor, so one stopped or waiting request never holds up another". It also lists "Requests go first" as a design goal.
- D13 delivers this for readiness only. A stopped first request slice holds the checkout, so a second request slice waits for it (`provider_not_done`).
- The design says the plan entry is amended, and the plan does carry the caveat at line 100. The architecture sentence is unchanged, so the two documents now disagree.
- 185 and 186 read the architecture. A reader will expect request-to-request independence at runtime, and 186's walkthrough could be designed to expect it.
- **Fix:** add a one-line amendment to `180-arch.program-coordination.md` (Principles, "Request slices live in one requests initiative…"), or record the deviation under its Deferred section. Name it as a consequence of the held-checkout cost, with separate request checkouts as the exit.

### [CONCERN] Crash adoption (D7 step 4) is under-specified and conflicts with the spawn ordering

- The journal write is step 6, the program-store `running` write is step 7, and the spawn is step 8.
- A crash between steps 6 and 7, or between 7 and 8, leaves a journaled entry with no spawned run.
- Step 4 says to "record it as `running` and launch nothing". It does not say how `slice_set`, `launch_head` and `target` are filled. `slice_set` is not among the journaled keys, and only `dispatch_check` carries the head.
- The by-id recovery observer will find no run and resolve the entry `not_applied`. The request then fails `run_lost` (D8), and the PM must resolve the asker's block.
- That outcome is defensible, because relaunch is deferred. But the Success Criteria say the next tick "adopts the entry", which implies the run continues, and "never launches a second" hides that the request dies.
- **Fix:** state the outcome for each crash window. Either say that adoption in these windows ends in `run_lost`, with the test asserting that, or move the spawn ahead of the `running` write. Also say what step 4 records, or that it records nothing and defers to the recovery path.

### [CONCERN] Internal inconsistencies in the request vocabulary and the bind signature

- **Wait on a `running` request.** D2 says `RequestWait` applies to `pending` and `replied` only (line 195). D8 (line 282) sets wait `unreadable` on a `running` request when the head read fails. The schema has no state-conditional `CHECK` on `wait`, so the rule is unenforced. Either allow `running` in D2 or give the head-read failure its own handling.
- **`bind_edge` signature.** D10 defines `bind_edge(edge_id, target, at)` (line 302). The API contract defines `bind_edge(request_id, target, at)` (line 399). The writer is used by the CAS test and by 185, so it needs a single signature.

### [NOTE] Proportionality

- Everything in the scope list traces to the slice plan entry or the architecture. This includes the edge-table rebuild, the `request` node kind, the hold refactor, `ProgramReadiness` and the config section. The effort of 4 matches the plan.
- The persisted wait taxonomy has seven waits, each stored with `evaluated_at`. If implementation runs long, `request_ahead` and `requests_unconfigured` are the cheapest to derive at listing time instead of storing. Both are needed on the blocked list, so this is only a fallback, not a required cut.

### Run Digest

- Response length: 5875 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 117940 / 11162 / 106774 / 7581 / not computed
- Duration: 63.1 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
