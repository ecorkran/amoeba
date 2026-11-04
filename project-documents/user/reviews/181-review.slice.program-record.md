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
reviewedSha: 8d83186524299ef04367f8e0e7ffc2398d656459
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 209862
cachedTokens: 104434
cacheWriteTokens: 105422
completionTokens: 5880
durationSeconds: 51.0
costUsd: 0.491785
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: hidden-dependency
    summary: "Member replacement leaves a referenced-member guard that no later slice owns"
    location: "project-documents/user/slices/181-slice.program-record.md#D3 — `register_program` replaces, `register_member` upserts; one program per project"
  - id: F002
    severity: concern
    category: scope
    summary: "Proportionality: 181 carries the largest refactor load in the initiative"
    location: "project-documents/user/slices/181-slice.program-record.md#Implementation Notes"
  - id: F003
    severity: note
    category: plan-alignment
    summary: "Program stage in 181 returns the program only; the plan entry says \"program and its members\""
    location: "project-documents/user/slices/181-slice.program-record.md#D7 — The program stage"
  - id: F004
    severity: note
    category: integration
    summary: "Stage sits before Observe; later readiness data will lag by one loop"
    location: "project-documents/user/slices/181-slice.program-record.md#D7"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for each new I/O path are enumerated"
    location: "project-documents/user/slices/181-slice.program-record.md#D6, #D7, #Data Flow"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Locality rule, dependency directions and parent amendments are consistent with the architecture"
    location: "project-documents/user/slices/181-slice.program-record.md#D1, #D4, #D9"
---

# Review: slice — slice 181

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Member replacement leaves a referenced-member guard that no later slice owns

D3 lets `register_program` replace a program whole, so a member left out of the body is deleted. It justifies this with "safe in 181 because nothing references a member yet; 183 and 184 add the rule for a member that edges or requests reference". D10 repeats the claim, and the Future Work item "Member and program removal" says re-registering is the correction path "until then".

The slice plan's 183 and 184 entries contain no such guard in their scope, success criteria or interfaces. Once edges and requests exist, a re-submitted `register_program` will silently orphan or delete a referenced member. That would break the architecture's rule that each cross-store transition is never lost and every wait stays explained. The parent architecture also defers "removing a member that edges or requests reference". Nothing at the slice-plan level assigns the interim protection.

Fix by doing one of these:
- Add a line to the 183 and 184 plan entries saying `register_program` rejects omitting a referenced member.
- Have 181 reserve a rejection code for it now.
- Make the "a replace must not drop a referenced member" rule explicit in 181's Interfaces under "Provides to Other Slices".

### [CONCERN] Proportionality: 181 carries the largest refactor load in the initiative

The plan entry is Effort 4, and the design says the five refactors in step 1 account for the jump over the original 3. Those refactors are the migrations parameterization, the connection-helper lift, the inbox drain extraction, the `resolve_checkout` move and the path-rule move. They are each justified by a concrete caller and are mitigated by "pure refactors committed on their own". The slice is still carrying a lot, and a few items could be cut or deferred:

- **The held `Program` result.** `ProgramStage.run` returns a `Program` that the tick holds and nothing reads until 183 (D7). D5 applies the opposite principle to the effective-mode computation: "added in 183 with its first caller". The stage's per-tick program store read has the same shape and no consumer in 181. The plan does assign the stage seam to 181, so keep the seam. Consider whether the held result and the `RunnerHost.program_store` plumbing wait for 183, leaving only the stage's place in the tick and its failure behaviour.
- **The `amoeba.program` package.** It exists to hold `read_member`, which only inspection calls in 181. It is justified by the import rule, so keep it, but state that it ships with exactly that one function.
- **`tick.py` extraction.** The conditional "extract `_launch_context` and the escalation-closing helper if over budget" makes the refactor scope open-ended. Decide up front, or cap it.

### [NOTE] Program stage in 181 returns the program only; the plan entry says "program and its members"

The slice plan's 181 entry says the stage "only finds the project's program and its members". D7 returns `Program | None` and opens no member store, deferring members to 183 (issue #26). This narrows the plan and is defensible, since nothing consumes members yet. Reconcile the plan entry's wording so 183's scope is unambiguous.

### [NOTE] Stage sits before Observe; later readiness data will lag by one loop

The architecture requires the program stage after resolutions and before readiness, and tolerates a one-loop lag for other members' data. D7 puts the stage before Observe. That is compatible, but 183 will feed readiness from this stage using the project's own snapshot, which will be a tick old. 183's design should say whether that is acceptable for a project's own edges.

### [PASS] Failure modes for each new I/O path are enumerated

Each new I/O path has explicit handling:
- **Program inbox files.** Invalid envelopes and payloads are quarantined. Store failures are counted and park the file at `inbox_max_attempts`, as for project submissions. Submitters get `SUBMISSION_REFUSED` before anything is written.
- **Program store at startup.** A corrupt or unreadable store is `STARTUP_FAILED`.
- **Program store in the stage.** A store failure propagates as a store failure and exits the process. D7 states plainly that this also stops projects in no program, and the architecture's explicit failure rule accepts that.
- **Member store reads.** `read_member` catches `StoreError` and returns `store_unreadable`. The cost bound is stated as busy timeout times member count, and in 181 only inspection pays it.
- **Atomic creation.** It reuses the `.creating`-then-rename path.

### [PASS] Locality rule, dependency directions and parent amendments are consistent with the architecture

- **D9.** It states the locality rule the architecture calls for: what the program store may hold, what it may not, read-only opens of other members' stores, and a single writer. It extends the contract proof with positive and negative checks.
- **D4.** It places the requests initiative index on the member registration, which is where the current architecture text puts it ("Each member's registration in the program record names the index"). It gives a reason: inspection does not load project config, so it could not otherwise compute the checkout reason.
- **Dependencies.** `amoeba.program` imports only `amoeba.store` and `amoeba.upstream`, and inspection does not import the Runner. One program per project is enforced both structurally (`UNIQUE`) and in code, with a named rejection.
- **`resolve_checkout`.** It resolves by worktree index range from the snapshot, not from plan contents. A member whose requests initiative does not exist yet therefore does not spuriously read as `checkout_unresolved`.

### Run Digest

- Response length: 6810 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 209862 / 104434 / 105422 / 5880 / not computed
- Duration: 51.0 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
