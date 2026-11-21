---
docType: review
layer: project
reviewType: slice
slice: local-work-through-the-hub
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/262-slice.local-work-through-the-hub.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: a03a06bae1946d9a97b40773046637e147d40d10
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 1183867
cachedTokens: 953340
cacheWriteTokens: 230511
completionTokens: 126251
durationSeconds: 562.5
costUsd: 0.581052
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: contract
    summary: "`send` changes in a way older clients cannot use, but the door version does not change"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:364-368"
  - id: F002
    severity: concern
    category: consistency
    summary: "A wake whose wrapper died after claiming counts under two rules"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:355"
  - id: F003
    severity: concern
    category: integration
    summary: "Cross-machine presence is built here, but the plan assigns it to 263"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:360"
  - id: F004
    severity: concern
    category: failure-modes
    summary: "A resume that started but never judged can be recorded as `not_delivered`"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:320-322"
  - id: F005
    severity: concern
    category: operations
    summary: "A hub blip during `wake_set_pid` ends a running woken agent"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:449"
  - id: F006
    severity: concern
    category: consistency
    summary: "The PM's install is described with three exceptions, but the local way changes in more ways"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:668"
  - id: F007
    severity: concern
    category: failure-modes
    summary: "A reply that does not validate has no stated handling"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:200"
  - id: F008
    severity: concern
    category: proportionality
    summary: "The `answer_too_large` branch is more than the case needs"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:211"
  - id: F009
    severity: concern
    category: operations
    summary: "The migration 013 undo discards every write since the update, and the walkthrough does not say so"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:764-766"
  - id: F010
    severity: concern
    category: consistency
    summary: "The verification walkthrough is marked as a draft and has the wrong `answer` form"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:672-689"
  - id: F011
    severity: note
    category: consistency
    summary: "The parent architecture needs updates the Departures table does not list"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:544-563"
  - id: F012
    severity: note
    category: operations
    summary: "The live-migration timing is hedged, and the new code's behavior on a schema-12 store is not stated"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:499"
  - id: F013
    severity: note
    category: integration
    summary: "`program_sources` is not placed"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:224"
  - id: F014
    severity: note
    category: operations
    summary: "`MAX_WORK_PER_CLAIM` does not say what happens to items beyond the cap"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:408"
  - id: F015
    severity: note
    category: integration
    summary: "The MCP `answer` on a joined machine has no deadline check until 263"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:509"
  - id: F016
    severity: pass
    category: alignment
    summary: "Both parent architecture checks are done, with each transaction and clock function listed"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:153-190"
  - id: F017
    severity: pass
    category: integration
    summary: "Interfaces from 260 and 261 match what those designs define, and the load NFR is restated"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:76-88"
---

# Review: slice — slice 262

**Verdict:** FAIL

> Verdict note: the frontmatter verdict is CONCERNS. The reviewer stated FAIL; its fail findings were fixed; all fifteen findings were checked 20261120; fourteen changed the design, one needed no change, see Resolution.
**Model:** claude-haiku-5-5

## Findings

### [FAIL] `send` changes in a way older clients cannot use, but the door version does not change

D8 makes `send` claim a due wake for the calling machine and return it, and the client starts `wake-run`. D15 and API Contracts (line 578) say the door version does not change, because only a call and fields are added. The parent's door section says the version changes when "an existing call changes in a way an older client cannot use" (architecture, "A door version"). Upgrades go hub first (parent walkthrough, step 10), so a 261 client on a 262 hub receives a wake it cannot start. That wake stays unended with no pid and blocks the member's next wake until `deadline_at`. Fix: bump the door version and its pinned-tuple test (260, line 309), or gate the wake claim on the `client_version` the hub already stores, and say which.

### [CONCERN] A wake whose wrapper died after claiming counts under two rules

Rule 2 excludes only an unended row with no pid past its deadline. The state table (line 144) says an unended wake "stops counting at its `deadline_at`", and the walkthrough (line 759) says a killed wrapper's row "stops counting at its deadline". A killed wrapper's row has its pid set, so rule 2 still counts it. It then blocks every wake of that member since the mark, until a new `send`. Make rule 2 match the table, and add a test for a pid-set row past its deadline.

### [CONCERN] Cross-machine presence is built here, but the plan assigns it to 263

The plan's 263 entry lists "the cross-machine presence that 262's waking reads" among what 263 provides (`user/architecture/260-slices.the-hub.md`, line 139). D8 says the presence check "is built and tested here", and Integration Points says it is "whole here" (line 611), with 263 only adding rows. Both cannot hold. Either the plan's 263 entry changes, or D8 states that it departs from the plan.

### [CONCERN] A resume that started but never judged can be recorded as `not_delivered`

If an attempt dies after `sq run --resume` has started and before it writes an outcome file, the next attempt finds no file, and the run is no longer at its pause. The design records `not_delivered` with the detail "an earlier attempt started and judged nothing". The answer was in fact delivered, so the record is wrong and the PM may answer again. The claim that "nothing on the machine can say" holds only because no start marker is written first. Write a `<answer seq>.started` marker before `sq run --resume`, in the same directory the prune removes, and give "started, no outcome" its own result rather than `not_delivered`.

### [CONCERN] A hub blip during `wake_set_pid` ends a running woken agent

D11 stops the `wake-run` process group when any step gets no reply. `wake_set_pid` runs after the agent has started, so a reply lost beyond the door's 30-second retry window ends a running agent session. The row then stays unended with no pid until its deadline. The parent says the wrapper "stops at that step and exits" (architecture, line 130), not that a running agent is killed. The walkthrough (lines 742-766) has no wake-during-outage case. Decide whether the wrapper stops the child, or only exits while the child runs to its own deadline, and walk that case.

### [CONCERN] The PM's install is described with three exceptions, but the local way changes in more ways

Integration Requirements say the PM's install "behaves as before, with three exceptions". The local way runs the same functions through `LocalSteps`, and the design changes it further. The pause claim goes stale at `answering_wait_seconds + 2 × CALL_BOUND_SECONDS` (line 549). The resume claim window changes (line 555). An oversize `question_settle` is refused "in both ways" (line 211; criteria line 640). The Migration Plan (line 573) already says tests that pinned the old values change. List these in Integration Requirements.

### [CONCERN] A reply that does not validate has no stated handling

`DoorSteps` "validates the reply" (line 200), but no failure is stated for a reply that fails validation, such as a missing key or a shape from a hub one version behind. D11 covers only `HubUnreachableError` and `HubRefusedError`. A new message type needs an explicit handling. State it: a named error that makes the command stop at that step (exit 3, error in the log), noting that a writing step may already have been applied.

### [CONCERN] The `answer_too_large` branch is more than the case needs

The design adds `StepTooLargeError`, a size check in both `Steps` implementations, a new `DeclineReason`, a catch in `handle-pause`, and a success criterion. It covers a case the design itself calls "unlikely", and the start cap already bounds that case at three answering runs. Cut candidate: delete the branch. An oversize settle then exits 3 like any other step failure, the claim goes stale, and the cap ends it. The cost is up to three answering runs on one oversize answer. The load test's per-step timing (line 527) is a second cut candidate.

### [CONCERN] The migration 013 undo discards every write since the update, and the walkthrough does not say so

Undo says `update_live.py restore` "puts the store back as it was before migration 013" (line 764). It does not say that restore discards every write since the update (answers, decisions, messages, sessions), and it does not say that the previous release must run against the restored store. So "Dead ends found: none" (line 766) is wrong for the upgrade. State what restore loses and the code rollback that goes with it.

### [CONCERN] The verification walkthrough is marked as a draft and has the wrong `answer` form

Line 672 says "Draft; refined after implementation", which leaves the acceptance demonstration open until the code exists. The command `amoeba answer --run <run id> --text ...` (line 689) does not match the CLI contract, which is `amoeba answer RUN_ID [--paused-at TIMESTAMP] --text ANSWER` (`docs/cli-contract.md:402`). Correct the form, state the expected output of each step now, and remove the draft label.

### [NOTE] The parent architecture needs updates the Departures table does not list

Parent walkthrough step 7 and its "Dead ends found: none" expect the flag to restart a `handle-pause` that died mid-pause. That holds only once a row exists (line 754). "Three kinds of operation" lists `answer` and `send` as whole-on-hub, but here each also starts a resume or wake in the same command. "A CLI call is a `cf` call plus one round trip" no longer holds for these paths (line 528). The parent can be wrong, so correct `260-arch` rather than leaving these as departures.

### [NOTE] The live-migration timing is hedged, and the new code's behavior on a schema-12 store is not stated

D14 says 261 "as written runs it right after its merge; either way" the script migrates. That leaves open when the PM's live store moves, while the Departures table (line 554) says release time. Also unstated is what the new code does when it opens a schema-12 store before the update runs. If it refuses, say so and say what the operator sees between merge and release.

### [NOTE] `program_sources` is not placed

261 says `program_sources` "runs only in the pause path, on the machine with the files... 262 keeps it client-run" (`user/slices/261-slice.members-by-name.md`, line 260). This design does not name it. `pause_sources` returns members and their checkout paths on the calling machine, which may be enough. Name the concept read and say it stays in the client part.

### [NOTE] `MAX_WORK_PER_CLAIM` does not say what happens to items beyond the cap

`claim_work` claims up to five items. The rest are handled because the flag stays true and the next call claims them, but that is implied. The Amoeba rule asks that every limit say what happens when it is hit. One sentence settles it.

### [NOTE] The MCP `answer` on a joined machine has no deadline check until 263

This is disclosed and matches the plan's 263 entry. In 262 only fixtures join, so nothing real is exposed yet. An MCP server started before a join runs `answer`, including a same-machine resume, with no deadline check. 263's check must land before any joined machine runs an MCP server.

### [PASS] Both parent architecture checks are done, with each transaction and clock function listed

D1 lists the transactions in the pause path and settle that run a check or read a local value, with each one's destination. D2 lists the store functions that take the time from the caller, the client-side comparisons, and a clock test. This is what the parent's Anticipated Slices section asks for.

### [PASS] Interfaces from 260 and 261 match what those designs define, and the load NFR is restated

Checked against the 260 and 261 designs: `CALL_BOUND_SECONDS` (43 = 30 + 3 + 10), `leave`, `rm --checkout`, `find_caller` and `find_member`, the `runs` document, the owner-trigger pattern, and the `not_served` refusal that D8 removes. The load NFR is restated with its targets (line 527). The call-count table in D16 (lines 530-540) is consistent with the latency targets.

### Run Digest

- Response length: 12838 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 1183867 / 953340 / 230511 / 126251 / not computed
- Duration: 562.5 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17

## Resolution

Resolved 20261120 in `user/slices/262-slice.local-work-through-the-hub.md`. Nothing was deferred and no issue was filed. Each finding was checked against the design and the source before it was acted on.

- [fail] `send` changes in a way older clients cannot use, but the door version does not change: changed. `DOOR_VERSION` becomes 2 and 260's pinned tuple with it, so the hub refuses an older client before anything is claimed for it. Stated in D8, D15, API Contracts, the departures table, the Migration Plan, a criterion and the walkthrough. Gating the claim on a body key was rejected as a second rule kept for clients that do not exist.
- [concern] A wake whose wrapper died after claiming counts under two rules: changed, wording only. The behavior was already consistent: a row with a pid is the mark's one wake, and at its deadline it stops being a live wake. Rule 2, rule 3, the state table and the walkthrough now say which "counting" each means, and a criterion covers a pid-set row past its deadline.
- [concern] Cross-machine presence is built here, but the plan assigns it to 263: changed. The read stays here, because `wake_due` is wrong without it and it is 244's existing check on the hub's one table; 263 provides the rows. D8 says so and the departures table has the row. The plan's 263 Interfaces line needs the matching wording (reported to the PM's agent; not edited here).
- [concern] A resume that started but never judged can be recorded as `not_delivered`: changed. The outcome file becomes an attempt file, written `started` before `sq run --resume` and then with the judged outcome. A later attempt that finds `started` and the run gone from the pause records `resumed` and starts nothing. Checking this also found that the old text replayed a stored `refused` and so stopped `handle-pause` from ever retrying a refused resume; a `refused` in the file is now never replayed. D6, D10, D11, D12, the departures table, three criteria and the walkthrough.
- [concern] A hub blip during `wake_set_pid` ends a running woken agent: changed. `wake_set_pid` with no reply is a warning and the wake goes on, as today's wrapper does when the store is held (`operations/wake_run.py`, `_record_pid`). A refusal still stops the command. D11 has one row per step, with what is left; D8, the departures table, a criterion and a walkthrough case follow.
- [concern] The PM's install is described with three exceptions, but the local way changes in more ways: changed. Integration Requirements lists eight differences.
- [concern] A reply that does not validate has no stated handling: changed. `StepReplyError`, handled exactly as no reply (D11), with a criterion; Integration Points no longer says the slice adds no error.
- [concern] The `answer_too_large` branch is more than the case needs: changed. The branch, `StepTooLargeError`, the decline reason and its criterion are deleted. An oversize settle is refused by the door, the command exits 3, and the start cap ends it as `starts_exhausted`. The per-step timing in the load test stays: the steps are new door calls and the latency target is theirs.
- [concern] The migration 013 undo discards every write since the update, and the walkthrough does not say so: changed. D14 and the walkthrough's Undo say what `restore` puts back (store, config and the previous commit, checked in `scripts/update_live.py`) and that everything written since is lost. It is listed as a third limit under "Dead ends found". The test writes a row between `update` and `restore`.
- [concern] The verification walkthrough is marked as a draft and has the wrong `answer` form: changed. The draft label is gone, the implementing agent runs it as the last task, each step has its expected output, and `answer` uses the contract's form, `amoeba answer <run id> --text ...`.
- [note] The parent architecture needs updates the Departures table does not list: changed. Three rows added (step 7 before the row exists, `answer` and `send` starting work in the same command, the call count). The matching text for `260-arch.the-hub.md` is reported; that file is not edited here.
- [note] The live-migration timing is hedged, and the new code's behavior on a schema-12 store is not stated: changed. D14 says the live store migrates at the release and never per merge, that nothing changes on the PM's install between merge and release, and that the new code migrates an older store when it opens it and never refuses one (`store/migrations.py`).
- [note] `program_sources` is not placed: changed. D5 says the gather, `program_sources` included, stays on the client and reads what `pause_sources` returns.
- [note] `MAX_WORK_PER_CLAIM` does not say what happens to items beyond the cap: changed. D10 says the rest is left unmarked, the `claim_work` reply's own flag stays true and the next call claims the next five, with a criterion.
- [note] The MCP `answer` on a joined machine has no deadline check until 263: no change. It is disclosed, the plan puts the check in 263, and `amoeba-mcp` does not start on a joined machine before 263.
- [pass] Both parent architecture checks are done, with each transaction and clock function listed: no change.
- [pass] Interfaces from 260 and 261 match what those designs define, and the load NFR is restated: no change.

Also checked: the example value 216.5 seconds (135.5 - 5 + 86) is right against `resume_bound_seconds`, the config example and `CALL_BOUND_SECONDS`. The walkthrough's "about four minutes" now gives the figure.

## Full-text review, 20261121

The whole design (all 827 lines, in order) was read against the architecture, the slice plan, the 260 and 261 designs, the cited parts of 263 and 264, and the code under `src/amoeba/`, `scripts/` and `tests/`. The migration order and the one-statement resume claim were run in a throwaway SQLite database. It found 3 important and 8 minor findings, none unverified. All eleven changed the design; none ended as "no change". Nothing was deferred and no issue was filed. The design's citations of 260 were also brought in line with 260 as of commit `9ee28aa5`.

- [important] The close sweep ran before the resume was handed out again, so `list`, `status` and the next pause's `handle-pause` marked a resumed answer `not_delivered` and the attempt file was never read: changed. The sweep leaves an answer with no outcome to its resume attempt, and judges only a `refused` answer, at `resume_claim_seconds`. D9, with D1, D4 step 1, D6, the state table, the departures table, the Migration Plan, four criteria and the walkthrough. One case still ends with a wrong record, as it does today, and D9 says so: a refused resume retried by `handle-pause` and killed after it started the run.
- [important] The MCP door lost the after-step in this slice, so an MCP `reply` or `cancel` no longer started the held question it released, on the PM's install, until 263: changed. The after-step runs on both doors, after every operation on the CLI door and after every operation but `answer` on the MCP door, as `start_after` does today. The MCP opt-out and the switch on `wiring.invoke` belong to 263. D10, Provides, Integration Requirements, the Migration Plan and a criterion.
- [important] The held-claim path lost the answer-limit check made before an answering run starts: changed. `pause_begin` reads the limit for a held row, and the held claim checks it before it gathers. D4 step 7, D5 and a criterion; the existing test passes unedited.
- [minor] `cf` was asked before the checks that skip without it today: changed. A run-only skip makes no `cf` call and sends `pause_begin` no caller. The answering-run skip now comes after `cf`, which is stated as the one change of order, with what a `cf` failure does. D4, D5 step 1, Integration Requirements, the Migration Plan and a criterion.
- [minor] Where a decline goes was stated two ways: changed. Every decline goes to `question_wait`; `question_settle` carries only an answer. Data Flow, D4, D5, and the too-large paragraph in D3, which now covers a decline's evidence.
- [minor] An unreachable hub cost more than one call bound: changed. After a command stops on no reply, the after-step makes no call. D10, D16 and a criterion.
- [minor] The prune's problems could not be both after the result and in it: changed. `handle-pause` and `status` keep their own prune call, with its problems in their result as today; the after-step prunes after every other operation and logs. D5 step 7, D10, D12 and a criterion.
- [minor] The counts of what migration 013 adds disagreed: changed. Six columns and three new values, in Technical Scope and D15; the store row of Component Structure lists the message modules.
- [minor] The `rm-machine` criterion was wider than D13: changed. It now says no question whose latest answer lacks a final outcome.
- [minor] "Every other operation and every step reads the config" was not true: changed. `work_problem` reaches any call whose own work needs no config, and `resume_record`, `wake_set_pid` and `wake_finish` load none on purpose. D10, a criterion and the walkthrough.
- [minor] Four places the implementer had to guess: changed, each with one rule.
  - How the pause path calls `add`: a `register` callable built by `wiring` (D5 step 3).
  - Where `resume-run`'s own log goes: `logs/resume-run/<seq>-<stamp>` (D10, D12).
  - Whether "claimed since that mark" includes the mark's own time: it does (D8 rule 2, a criterion).
  - Whether an unreadable first poll overwrites `started` in the attempt file: it records nothing and leaves the file (D6, a criterion).

Outside changes this leaves, reported and not made here: 263's amendment row for 262 D10 and its D7 must say that 263, not 262, takes the after-step off the MCP door and adds the switch on `wiring.invoke`.
