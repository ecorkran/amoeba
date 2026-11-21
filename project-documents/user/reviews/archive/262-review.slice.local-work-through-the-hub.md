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
reviewedSha: 349a1e9329f2df77d0075898be5c155a653bb93d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 1321136
cachedTokens: 1102996
cacheWriteTokens: 218122
completionTokens: 108754
durationSeconds: 490.5
costUsd: 0.529899
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: concurrency
    summary: "Stale-claim restart does not say which claim it replaces"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:223"
  - id: F002
    severity: concern
    category: schema-migration
    summary: "The migration's insert trigger can abort the copy of pre-migration rows"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:468-470"
  - id: F003
    severity: concern
    category: state-exit
    summary: "The prune trigger differs from the parent and leaves wake and resume logs unpruned"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:438-440"
  - id: F004
    severity: concern
    category: state-exit
    summary: "A resume that keeps dying before it starts has no cap"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:401"
  - id: F005
    severity: concern
    category: architecture-principle
    summary: "Removing a machine leaves paths on history rows with no machine"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:451-452"
  - id: F006
    severity: concern
    category: scope
    summary: "The wake retry after a failed start is new scope and changes daily use"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:343"
  - id: F007
    severity: concern
    category: proportionality
    summary: "The answer-too-large path may cover a case that cannot occur"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:206-207"
  - id: F008
    severity: concern
    category: hidden-dependency
    summary: "A command started with a client file can run later steps on the local store"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:709"
  - id: F009
    severity: concern
    category: operator-walkthrough
    summary: "The walkthrough's undo leaves hub waits with no named exit"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:732-734"
  - id: F010
    severity: concern
    category: failure-modes
    summary: "The outcome file and the losing paths are not specified"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:301-303"
  - id: F011
    severity: note
    category: architecture-alignment
    summary: "The resume claim uses the full call bound, where the parent says the retry time"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:283"
  - id: F012
    severity: note
    category: scope
    summary: "The live-store departure rests on a rule the review cannot see"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:531"
  - id: F013
    severity: pass
    category: architecture-alignment
    summary: "The two checks the parent left to this slice are done"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:153-190"
  - id: F014
    severity: pass
    category: integration
    summary: "Interfaces with 260 and 261 match their designs"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:76"
  - id: F015
    severity: pass
    category: scope
    summary: "The success criteria cover the plan's 262 entry, and nothing in scope is deferred"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:590-616"
---

# Review: slice — slice 262

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Stale-claim restart does not say which claim it replaces

`question_replace_claim` "swaps a dead claim's answering run," and D5 runs it before the answering run (line 263). Line 247 says each replaced transaction keeps today's compare-and-set, but no step's request says what that compare-and-set matches. `pause_begin` returns the row with `claim_stale` (line 245), but nothing says the replace must match the claim it read. Two callers can both see the claim as stale: a `handle-pause` started by `claim_work` (line 394 takes the start mark, not the claim), and the hook's own `handle-pause`. If the replace does not check the claim's identity, both replace it and both run the answering model. `question_settle`'s "superseded" (line 225) stops only the second write. The success criterion at line 595 and the risk at line 677 require one taker. State that the request carries the claim identity, that a lost compare-and-set returns `lost`, and that a `lost` command runs nothing, as `question_claim_held` does (line 222).

### [CONCERN] The migration's insert trigger can abort the copy of pre-migration rows

The `BEFORE INSERT` trigger aborts when `machine_id` is null. Every row the table rebuild copies has a null machine until `open_state_store` sets `local` on first open (line 472). Triggers fire on `INSERT ... SELECT`, so the copy fails if the new trigger exists when it runs. Line 470 says the rebuild carries the triggers the tables have "by then," which does not say the new one is created after the copy. This would fail the live migration (line 476) and the `update`/`restore` test. Specify the order (copy, then create the trigger) and test it on a schema-12 copy that has rows.

### [CONCERN] The prune trigger differs from the parent and leaves wake and resume logs unpruned

D12 says prune "keeps its trigger," at the end of `handle-pause` and `status`. The walkthrough repeats this (line 731). The parent says today's trigger is "at most once an hour, from any call" (260 architecture, line 177). The 220 architecture says only that `status` prunes (line 175). The design cites neither source and lists no departure. `wake-run` and the resume write logs (the wake's `log_stem` and the outcome file), but neither triggers a prune. On a machine where no `handle-pause` or `status` runs, those logs are never removed, and the design gives no reason they are bounded. Adopt the parent's "from any call," or cite the source for today's trigger, record the change in Departures, and name the cleanup for wake and resume logs.

### [CONCERN] A resume that keeps dying before it starts has no cap

Automatic `handle-pause` starts are capped at three because "a start can fail every time" (line 401). The same reasoning applies to resumes, but `claim_resume` has no count (lines 276-283). A loop needs each attempt to die before it starts `sq run --resume`. Then there is no outcome file, the run is still at pause, and each later call from that machine hands out the resume again after `resume_claim_seconds`, without limit. Once an attempt does start `sq`, the next attempt records `not_delivered` and the loop ends. The answer can still stay `answered` with no outcome until someone runs `dismiss`. Give resumes the same `start_count` cap, or state why early deaths are bounded.

### [CONCERN] Removing a machine leaves paths on history rows with no machine

The parent says "a path means nothing without its machine," and every stored path is stored with its machine (260 architecture, line 63). D13 sets `machine_id` to null on wake rows that keep their `log_stem`. D8 says `list` shows a wake's path with its machine (line 351), so after `rm-machine` it shows a path with no machine. Questions keep the machine's name in their detail (line 449). Wakes do not. The null is needed because 260 deletes the machine row (260 design, line 428). Fix the path, not the row: put the machine's name in the wake's detail, and clear `log_stem` on rows that `rm-machine` ends.

### [CONCERN] The wake retry after a failed start is new scope and changes daily use

Neither the plan's 262 entry nor its success criteria ask for a retry. The parent says a request with no waking machine "waits for the next agent or its expiry, exactly as a member without a wake command does today" (260 architecture, line 198). Its goal is "Daily use does not change" (line 39). The design adds the retry and lists it as a change to the PM's install (line 637). It also adds a rule-2 branch for `start_failed` (line 336) and a success criterion (line 607). The departures row at line 530 attributes "never tried again" to the parent, which the 260 text does not say. The lighter option is to end a failed wake and let the next `send` decide, as the parent describes. Rule 2 then becomes "any wake claimed since the mark." Cut the retry, or justify it against the goal.

### [CONCERN] The answer-too-large path may cover a case that cannot occur

`MAX_CALL_BYTES` is 1 MiB (260 design, line 266). The path adds a `StepTooLargeError`, a new `DeclineReason`, a special case in `handle-pause`, and a success criterion. The design says the document can exceed the limit only through the answer and its evidence. It does not bound either. Evidence is limited by the passage bound (line 245), which is not quantified. State the bound that makes 1 MiB reachable. If it is not reachable, cut the path. The start cap already ends a settle that never fits, at the cost of up to three answering runs. If the design keeps the path to avoid that cost, it should say so.

### [CONCERN] A command started with a client file can run later steps on the local store

The design says a child whose client file is removed "goes to the local store, where its row does not exist, so it fails loudly." That is not guaranteed. `leave` restores a set-aside store (260 design, lines 234 and 240). That store holds the machine's pre-join rows, and may hold the same run's question. The child could then claim or settle against stale data. This conflicts with the parent's "never falls back to anything local" (line 37). Have each command record its mode when it starts, and refuse any later step that would run locally. The "fails loudly" claim then holds by construction.

### [CONCERN] The walkthrough's undo leaves hub waits with no named exit

"Undo" says `amoeba leave` "goes back to the local store." It does not say what happens to the hub's waiting work for that machine: answered resumes, claimed and held questions, and due wakes. That machine can no longer end them. Their exits are `dismiss`, expiry, or `rm-machine`, and 260 says `rm-machine` is a separate step (260 design, line 240). The walkthrough names none of these, so "Dead ends found: none" (line 734) does not hold. Name the exit: run `rm-machine` after `leave`, which closes the machine's waits as `machine_removed`. Also say where a fresh join returns, since it has no set-aside store and so returns to an empty local store.

### [CONCERN] The outcome file and the losing paths are not specified

The outcome file is a new I/O path, and the design gives it no failure mode. If the write fails, the next attempt's "no file" branch records `not_delivered` for a resume that may have run. That is a wrong outcome, not a crash. Also unspecified: the losing path of `question_insert` when two `handle-pause` calls insert the same run and paused time, which is the question's key (line 188). State what a failed write does and whether it is retried, and give the losing path of each claim step. Write the file to a temp name and rename it, so a reader never sees a partial file.

### [NOTE] The resume claim uses the full call bound, where the parent says the retry time

The parent says the resume claim allows "the network retry time in place of the one local store wait" (260 architecture, line 189). The design uses `2 * CALL_BOUND_SECONDS` (43 s, which is retry plus connect plus read, per 260 design line 304). That is more conservative and the rationale is sound, but Departures does not record it.

### [NOTE] The live-store departure rests on a rule the review cannot see

The departures row says the PM's "standing rule" moves the live update to release time. The plan says schema changes land on the local store as they come (260 slice plan, line 27). The rule is not in the documents under review, so the design should cite where it is recorded. The release step is covered in the walkthrough (line 721).

### [PASS] The two checks the parent left to this slice are done

D1 lists the transactions in the pause path, the settle, the resume, `answer` and the wake step that run a check or read a local value inside them. D2 lists the store functions that take the time from their caller and the sweeps that compare a client's time with a store time, and moves each to the hub. Both match the parent's note (260 architecture, lines 301-303). A test walks the request models for time fields (line 118).

### [PASS] Interfaces with 260 and 261 match their designs

The values and names this slice depends on match the source designs: `CALL_BOUND_SECONDS` is 43 (260 design, line 304); `rm-machine` deletes the machine's row (260 design, line 428); `rm --checkout` exists (261 design, line 308); the `not_served` refusal for a wake-sending `send` is what 262 removes (261 design, line 322); and `handle-pause`, `wake-run` and `answer` are listed as not yet served (261 design, line 379). The one input 262 lacks from joined machines is their session rows, which 263 writes, as the design states (line 341).

### [PASS] The success criteria cover the plan's 262 entry, and nothing in scope is deferred

Each criterion in the 262 plan entry has a matching criterion here: the three-caller tests, the lost-reply limit, the hub stopped mid-pause, the 242 and 244 fixtures, the expiry of a wake with no machine, the answer limit under two settles, the clock test, and the cleanup past `prune_after_days`. The exclusions (263, 264, 320) are the ones the plan assigns to those slices.

### Run Digest

- Response length: 13907 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1321136 / 1102996 / 218122 / 108754 / not computed
- Duration: 490.5 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
