---
docType: review
layer: project
reviewType: slice
slice: program-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/181-slice.program-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 801eb22b41d420f193d20f3b84c5fd7306495412
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 113066
cachedTokens: 11162
cacheWriteTokens: 101900
completionTokens: 5614
durationSeconds: 47.5
costUsd: 0.465704
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: architectural-alignment
    summary: "D4 moves the requests initiative index out of project config, which contradicts the architecture and slice plan"
    location: "project-documents/user/slices/181-slice.program-record.md:164-172"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Part of the slice has no consumer in 181 and can be cut or deferred"
    location: "project-documents/user/slices/181-slice.program-record.md:179, 207, 391-421"
  - id: F003
    severity: note
    category: failure-modes
    summary: "A program store failure exits the process even for projects in no program"
    location: "project-documents/user/slices/181-slice.program-record.md:204-205"
  - id: F004
    severity: note
    category: failure-modes
    summary: "Member read timing is described as free, but a busy member store can stall the tick"
    location: "project-documents/user/slices/181-slice.program-record.md:196-197"
  - id: F005
    severity: note
    category: dependencies
    summary: "Frontmatter dependencies omit slices the doc relies on"
    location: "project-documents/user/slices/181-slice.program-record.md:6-10"
  - id: F006
    severity: pass
    category: architectural-alignment
    summary: "Layering, dependency direction and ownership match the architecture"
    location: "project-documents/user/slices/181-slice.program-record.md:90-135"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated with explicit handling"
    location: "project-documents/user/slices/181-slice.program-record.md:115-128, 181-198"
  - id: F008
    severity: pass
    category: boundaries
    summary: "Locality rule change and proof are scoped and testable"
    location: "project-documents/user/slices/181-slice.program-record.md:220-226"
---

# Review: slice — slice 181

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D4 moves the requests initiative index out of project config, which contradicts the architecture and slice plan

The architecture says "Each member's project config names the index of its requests initiative (no default)". The slice plan repeats this in its 181 entry ("Each member's project config gains the index…"), its Interfaces line and its "Configuration lands where it is first read" note. D4 puts the index on the member registration in the program store instead, and says it "supersedes that wording".

The reasoning holds up. `amoeba inspect` does not load project config, so it could not compute the `checkout_unresolved` reason the plan requires. The alternatives were a new status table or a new `inspect` flag. Putting the index in the program record also keeps one source for the stage and for inspection.

The problem is that the parent documents still say the opposite. 184 and 185 are designed against the architecture and the plan, so they will read "project config" and reach a different conclusion than 181. Before this slice is accepted, amend three places:
- the architecture's "Request slices live in one requests initiative" bullet;
- the slice plan's 181 entry, including its Interfaces line;
- the plan's configuration note.

Also say that 184's "pipeline models and cost cap come from per-project configuration" is unaffected.

### [CONCERN] Part of the slice has no consumer in 181 and can be cut or deferred

The slice is large: three extractions, a new package, a new store class, a second inbox tenant, three listings, a new column on `inbox`, two moves of existing code and a contract-proof change. Most of it is needed. Four pieces are not:

- **`ProgramStore.consumption_mode()`** (D5, line 179) has no caller in 181. The doc says "183 is its first caller; 181 tests it directly." The overrides table and registration are 181's scope, since the architecture assigns consumption modes and per-pair overrides to the program record. The effective-mode computation can move to 183, where it will be used and shaped by the real caller.
- **Per-tick member reads in the stage** (D7, lines 204 and 207). Nothing consumes the `ProgramView`, and inspection recomputes readability itself through `read_member` (Data Flow, "Inspection"). Every project tick in a supervisor with a program store therefore pays up to sixteen read-only opens, and gains a failure surface, for no output in 181. The slice plan does assign "reads members and reports unreadable" to the stage, so this is a trade-off to weigh. A lighter option is to ship the stage seam (find the project's program, return a `ProgramView` holding the member list) and add the member state when 183 first consumes it. `read_member` stays shared with inspection either way.
- **Verification step 5** needs a live CF watch to record an observed snapshot. That is live-walkthrough work, which belongs to 186. Tests already cover each reason using fixtures written by the tests. Trim step 5 to the cases that need no live CF.
- **The walkthrough as a whole** (eight steps) restates the Functional Requirements. It can be shortened.

### [NOTE] A program store failure exits the process even for projects in no program

The architecture lists as a goal that a project in no program "behaves exactly as it does after 140, whatever happens to any program". It also says a program store failure "exits the process". The slice follows the second statement. Every project's tick reads the program store to find its program, so a corrupt program store stops every project. A bad `programs.sqlite3` is also `STARTUP_FAILED` for the whole supervisor.

This follows the architecture's explicit failure rule and is covered by a Success Criterion and Verification step 7. The two architecture statements still conflict, and the slice does not mention it. Add one sentence to D7 acknowledging that "unchanged after 140" holds only while the program store is healthy.

### [NOTE] Member read timing is described as free, but a busy member store can stall the tick

D6 says "No subprocess is started… the stage spends no tick budget and needs no timeout". `StoreBusyError` is also listed as a `store_unreadable` cause ("busy past the timeout"). A read-only open waits up to that busy timeout, so one busy member can delay every member's tick. State the bound, namely the existing store busy timeout times the member count, or confirm that the resident process is the only writer so contention cannot occur in the stage.

### [NOTE] Frontmatter dependencies omit slices the doc relies on

"Interfaces Required" names slice 128 (`resolve_checkout`, `cf_links`, `latest_cf_snapshots`) and the project store schema version of 15 "after 144". The slice also reuses 140's blocked rows. The frontmatter `dependencies` lists only 101, 103, 122 and 123. Add 128 and 144, or state that 120 and 140 are covered as whole initiatives.

### [PASS] Layering, dependency direction and ownership match the architecture

The design keeps coordination in the Runner's tick as a stage, with no new tenant or process and no new `sq`, `cf` or `git` command. The stage sits after resolutions and before Observe, as the architecture orders it. The program store is a separate class with its own schema line, so "no project rows in the program store" is structural rather than a convention. `amoeba.program` imports only `amoeba.store` and `amoeba.upstream`. This respects the rule that inspection may not import `amoeba.runner`. Writes stay with the resident process, and the writer guard extends to `ProgramStore.open`.

### [PASS] Failure modes for the new I/O paths are enumerated with explicit handling

The doc covers the following paths:
- Registration: validation refusal before write, quarantine reasons, first-wins ids, a transactional apply with `applied` or `rejected` records, and attempt counting with parking.
- Atomic store creation, using the same `.creating` rename as project stores.
- Member readability: a closed six-reason vocabulary, in a fixed order, with a specific-exception catch and a comment as the exception rule requires.
- Program store failure: exits as a store failure, or `STARTUP_FAILED` at start.

Each path has a named test or walkthrough step. The architecture states no numeric NFRs, so none need restating.

### [PASS] Locality rule change and proof are scoped and testable

The locality rule change matches the architecture's "Technical Considerations". It allows programs, members, modes and submissions, and bars any project's nodes, blocks or questions. A project's tick may open other members' stores read-only. The proof gains positive and negative checks. Placing the store in a subdirectory avoids a collision with a project's `{project_id}.sqlite3` and with `discover_project_ids`.

### Run Digest

- Response length: 7653 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 113066 / 11162 / 101900 / 5614 / not computed
- Duration: 47.5 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
