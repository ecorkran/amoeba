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
reviewedSha: e04ac7f36c7e2955576ee689915e0217fb0e3922
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 111106
cachedTokens: 11162
cacheWriteTokens: 99940
completionTokens: 7448
durationSeconds: 63.9
costUsd: 0.476207
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Core coordination rules match the architecture"
    location: "project-documents/user/slices/184-slice.request-runs.md:39-51"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Layer placement of the band check and the program-store writers"
    location: "project-documents/user/slices/184-slice.request-runs.md:225-234, 375-380"
  - id: F003
    severity: concern
    category: layer-boundary
    summary: "`ProgramReadiness` is defined in a layer that lifecycle and intent must not import"
    location: "project-documents/user/slices/184-slice.request-runs.md:119-124, 324-332, 419-426"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Two failure paths for a run that never started, and `bind_edge`'s False result has no handling"
    location: "project-documents/user/slices/184-slice.request-runs.md:261-264, 279-289, 303-312, 494"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Proportionality: several mechanisms can be cut or folded without losing the slice's deliverable"
    location: "project-documents/user/slices/184-slice.request-runs.md:174-215, 253-272, 507"
  - id: F006
    severity: note
    category: consistency
    summary: "State Management says request rows are written only by the provider's tick, but `create_request` is the asker's write"
    location: "project-documents/user/slices/184-slice.request-runs.md:165-167, 179"
  - id: F007
    severity: note
    category: scope
    summary: "The slice-plan amendment in D13 is not a listed task"
    location: "project-documents/user/slices/184-slice.request-runs.md:339-340, 555-561"
---

# Review: slice — slice 184

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core coordination rules match the architecture

The provider's tick owns the request from creation to close, as the architecture's "Work in the provider" paragraph says. The recorded slice set and the plan-read-gated binding check carry out the architecture's "bound only when the next plan read shows a slice at the reported index absent from the recorded set." The already-met reply binds only to evidence, and 183's observation still decides release, so "nothing a model says satisfies an edge" holds. A PM resolution on the asker's block withdraws the request (D10), as the architecture's "PM's answer always wins" requires. A request run reuses the existing journal, spawn and observer machinery (`sq_request` follows `sq_answer`), and Amoeba never edits a plan or repo itself. D13 states where the architecture's shared-checkout cost applies, and the architecture already cites "184, D13" for it.

### [PASS] Layer placement of the band check and the program-store writers

`program/band.py` is pure and imports only `amoeba.store` and `amoeba.upstream`. Both the provider's launch and 185's answering stage can call it, which is the dependency direction the architecture's "declines up front" rule needs. The journal and node live in the provider's own store (D3), so 181's locality rule and per-store recovery both hold. The rejected alternatives are stated.

### [CONCERN] `ProgramReadiness` is defined in a layer that lifecycle and intent must not import

The doc says `runner/lifecycle` "never imports the program store" and "receives node-id sets" (183's principle, restated by the architecture). The API contract, though, defines `ProgramReadiness` in `runner/program/stage.py`, the module that holds the program store seam. D12 passes it into `predecessors.slice_predecessor`, `governance.governing` and `current_slices`. Those live in `runner/lifecycle` and `intent/`. Either those modules import `runner.program.stage` (a transitive import of the program store, which the purity and import checks should reject), or the dataclass's real home differs from what the contract shows.

Fix: put `ProgramReadiness` in a neutral module that lifecycle and intent own, such as `runner/lifecycle/readiness.py`. The program stage would populate it. Or pass the three frozen sets as separate arguments. State which, and add the import-boundary test to the Technical Requirements.

### [CONCERN] Two failure paths for a run that never started, and `bind_edge`'s False result has no handling

D8's table fails any non-`completed` run, "vanished" included, as `run_failed`. D7 step 4 and the crash-recovery criterion expect a never-spawned run to fail `run_lost` after recovery resolves the entry `not_applied`. After a crash between step 7 and step 8, the stage's step 1 polls an unresolved `sq_request` entry whose run does not exist.

The doc does not say whether that poll treats the run as vanished and fails it `run_failed` immediately, or waits out the launch grace for recovery. The acceptance test asserts `run_lost`, and the D8 table could produce `run_failed`. That is a race between the stage and recovery, with the outcome decided by tick order.

Fix: state that the stage does not treat a vanished run as failed while its entry is unresolved and inside the launch grace. Alternatively, map "vanished before grace expiry" to the recovery path explicitly.

`bind_edge` returns `False` when the edge is no longer open and unbound. D10 says it "returns False and writes nothing," but neither D9 nor D8 says what the stage then does with the `replied` request or the `already_met` run. The criterion implies `withdrawn`. Pin it for both callers, because supersession racing a bind is the case D10 exists for.

### [CONCERN] Proportionality: several mechanisms can be cut or folded without losing the slice's deliverable

The slice delivers the provider side of requests, but it adds seven states, seven waits, nine failures, a new node kind, a new journal kind, an edge-table rebuild, a hold refactor, a config section and probe wiring, at relative effort 4. Cuts to consider:

- **Stored duplicates.** `provider_project` copied from the edge, plus a test pinning the equality. `requests_index` and `target` stored per request, though they come from the member record and project config. `io_dir` is derivable from `<supervisor_dir>/requests/<run_id>/`. `reply_commit` and `reply_kind` partly duplicate the edge target. Keep only what recovery and the listing read.
- **Wait vocabulary.** `request_ahead` is shadowed by `checkout_in_use` for any `running` request. The "first match wins" order puts `checkout_in_use` first, so `request_ahead` only ever shows for `replied`. Fold the two, or drop `request_ahead` and let `replied` carry its own reason.
- **D7 step 4 ("adopt an earlier attempt").** Every crash window it handles ends in `run_lost` or normal finishing, with no relaunch. Writing the program-store `running` row from the entry could be the observe step's job. That would drop the separate adoption branch and shrink the crash test matrix.
- **Restated material.** The "Interfaces Required" lists name dozens of 120, 181 and 183 functions, and the Component table, Data Flow and Overview repeat each other. Trim these to the changed seams.

None of these changes behavior the architecture requires.

### [NOTE] State Management says request rows are written only by the provider's tick, but `create_request` is the asker's write

D1 and the data-flow diagram show `create_request` called in the asker's tick (185). The architecture also assigns request creation to B's tick. The "Request rows are written only by the provider's tick" line should say "created by the asker's tick, then written only by the provider's tick." This matters because the locality proof and the contract doc in `store-contract.md` will quote the writer rule.

### [NOTE] The slice-plan amendment in D13 is not a listed task

D13 says the slice plan's criterion "a second request slice is not held up by a stopped first one" is amended to readiness only. The architecture already matches (line 53), so this is not a scope reduction against it. The amendment is not in the Development Approach or the docs list, though, and could be forgotten. Add it to step 7.

### Run Digest

- Response length: 7069 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 111106 / 11162 / 99940 / 7448 / not computed
- Duration: 63.9 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
